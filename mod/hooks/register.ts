import type { EngineInterface, Register } from 'claude-code'

// 大小姐的心情，对应 Claude 此刻在做什么
type Mood = 'idle' | 'thinking' | 'working' | 'asking' | 'done' | 'ended'

// 调用这些工具时，是在等用户回答或拍板：大小姐举手
const ASKING_TOOLS = new Set(['AskUserQuestion', 'ExitPlanMode'])

const s = {
  file: undefined as string | undefined,
  launcher: undefined as string | undefined,
  cwd: '',
  mood: 'idle' as Mood,
  since: 0,
  inTurn: false,
  tools: 0,
  asking: 0,
  waitingForPerson: new Set<string>(),
  rateLimits: [] as unknown[],
  cost: undefined as number | undefined,
  writing: Promise.resolve() as Promise<void>,
}

// 状态文件写在项目文件夹的 state/sessions/ 里，桌面上的小窗口从那里读
async function locate($: EngineInterface) {
  const stat = await $.fs.stat($.plugin.root, { resolve: true }).catch(() => undefined)
  const real = (stat?.realPath ?? $.plugin.root).replace(/[\\/]+$/, '')
  const project = real.replace(/[\\/][^\\/]*$/, '')
  s.file = `${project}/state/sessions/${await $.session.id()}.json`
  s.launcher = `${project}/overlay/launch.cmd`
}

function save($: EngineInterface, next: Mood) {
  if (next !== s.mood) {
    s.mood = next
    s.since = Date.now()
  }
  const { mood, since, rateLimits, cost, cwd, file } = s
  const text = JSON.stringify({ mood, since, updated: Date.now(), rateLimits, cost, cwd })
  s.writing = s.writing
    .then(() => (file ? $.fs.write(file, text) : undefined))
    .catch(err => $.ui.log(`state write failed: ${String(err)}`, { to: 'debug' }))
  return s.writing
}

function refresh($: EngineInterface) {
  return save($, s.asking > 0 ? 'asking' : s.tools > 0 ? 'working' : s.inTurn ? 'thinking' : s.mood)
}

function resetTurn() {
  s.tools = 0
  s.asking = 0
  s.waitingForPerson.clear()
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const started = await next(e)
    s.cwd = e.cwd
    await locate($)
    const usage = await $.session.usage().catch(() => undefined)
    s.rateLimits = usage?.rateLimits ?? []
    s.cost = usage?.cost?.usd
    await save($, 'idle')
    // 叫醒桌面上的大小姐；她自己会确认只开一个，并在 Claude 关掉时离开
    if (s.launcher) {
      await $.process
        .run(['cmd.exe', '/d', '/c', s.launcher], { timeoutMs: 15000 })
        .catch(err => $.ui.log(`overlay launch failed: ${String(err)}`, { to: 'debug' }))
    }
    return started
  })

  on('turn.start', async ($, e, next) => {
    if (e.agentId === undefined) {
      s.inTurn = true
      resetTurn()
      await save($, 'thinking')
    }
    return next(e)
  })

  // 等用户点"允许"的工具调用：验证结果是 ask 时记下来，直到这次调用结束
  on('tool.check', async ($, e, next) => {
    const verdict = await next(e)
    if (verdict.decision === 'ask' && e.tool_use_id && e.agentId === undefined && !ASKING_TOOLS.has(e.tool)) {
      s.waitingForPerson.add(e.tool_use_id)
      s.asking++
      await refresh($)
    }
    return verdict
  })

  on('tool.call', async ($, e, next) => {
    const isAsking = ASKING_TOOLS.has(e.tool) && e.agentId === undefined
    if (isAsking) s.asking++
    else s.tools++
    await refresh($)
    try {
      return await next(e)
    } finally {
      if (isAsking) s.asking--
      else s.tools--
      if (e.tool_use_id && s.waitingForPerson.delete(e.tool_use_id)) s.asking--
      s.asking = Math.max(s.asking, 0)
      s.tools = Math.max(s.tools, 0)
      await refresh($)
    }
  })

  on('turn.complete', async ($, e, next) => {
    if (e.agentId === undefined) {
      s.inTurn = false
      resetTurn()
      await save($, e.isAborted ? 'idle' : 'done')
    }
    return next(e)
  })

  on('session.measure', async ($, e, next) => {
    s.rateLimits = e.rateLimits
    s.cost = e.cost?.usd
    await refresh($)
    return next(e)
  })

  on('session.end', async ($, e, next) => {
    await save($, 'ended')
    return next(e)
  })
}
