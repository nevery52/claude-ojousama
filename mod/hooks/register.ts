import type { EngineInterface, Register } from 'claude-code'

// 大小姐的心情，对应 Claude 此刻在做什么
type Mood = 'idle' | 'thinking' | 'working' | 'asking' | 'done' | 'ended'

// 调用这些工具时，是在等用户回答或拍板：大小姐举手
const ASKING_TOOLS = new Set(['AskUserQuestion', 'ExitPlanMode'])

// 大小姐头顶的气泡：只写事实，Claude 正在做什么
type Activity = { text: string; at: number; end?: number }

function basename(path: unknown) {
  return typeof path === 'string' ? path.split(/[\\/]/).pop() || path : ''
}

function describe(tool: string, input: Record<string, unknown>): string | undefined {
  const file = basename(input.file_path ?? input.notebook_path ?? input.path)
  switch (tool) {
    case 'Read':
      return file ? `在读 ${file}` : '在读文件'
    case 'Edit':
    case 'MultiEdit':
    case 'NotebookEdit':
      return file ? `在改 ${file}` : '在改文件'
    case 'Write':
      return file ? `在写 ${file}` : '在写文件'
    case 'Bash':
    case 'PowerShell':
      return '在运行命令'
    case 'Grep':
      return '在搜索代码'
    case 'Glob':
      return '在找文件'
    case 'WebSearch':
      return '在上网查资料'
    case 'WebFetch':
      return '在看网页'
    case 'Agent':
    case 'Task':
      return '请了个帮手'
    case 'Skill':
      return '在翻说明书'
    case 'AskUserQuestion':
      return '有问题想问你'
    case 'ExitPlanMode':
      return '想请你看看计划'
  }
  if (tool.startsWith('mcp__Claude_Browser__') || tool.startsWith('mcp__claude-in-chrome__')) return '在用浏览器'
  if (tool.startsWith('mcp__ccd_turn__')) return undefined   // 更新任务清单之类，不值得说
  return '在用工具'
}

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
  activity: undefined as Activity | undefined,
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
  const { mood, since, rateLimits, cost, cwd, file, activity } = s
  const text = JSON.stringify({ mood, since, updated: Date.now(), rateLimits, cost, cwd, activity })
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
      s.activity = undefined
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
      s.activity = { text: '需要你确认一下', at: Date.now() }
      await refresh($)
    }
    return verdict
  })

  on('tool.call', async ($, e, next) => {
    const isAsking = ASKING_TOOLS.has(e.tool) && e.agentId === undefined
    if (isAsking) s.asking++
    else s.tools++
    const text = describe(e.tool, e as Record<string, unknown>)
    const activity: Activity | undefined = text ? { text, at: Date.now() } : undefined
    if (activity && !(s.asking > 0 && !isAsking)) s.activity = activity
    await refresh($)
    try {
      return await next(e)
    } finally {
      if (activity && s.activity === activity) activity.end = Date.now()
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
      const now = Date.now()
      s.activity = e.isAborted ? undefined : { text: '做完啦', at: now, end: now }
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
