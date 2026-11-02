import type { EngineInterface, Register } from 'claude-code'

// 大小姐的心情，对应 Claude 此刻在做什么
type Mood = 'idle' | 'thinking' | 'working' | 'asking' | 'done' | 'ended'

// 调用这些工具时，是在等用户回答或拍板：大小姐举手
const ASKING_TOOLS = new Set(['AskUserQuestion', 'ExitPlanMode'])

// 大小姐头顶的气泡：只写事实，Claude 正在做什么
type Activity = { text: string; at: number; end?: number; error?: boolean; proud?: boolean }

const HISTORY_SIZE = 10        // 悬停时能看到最近几件事
const NIGHT_NOTE_EVERY = 3600_000   // 深夜报时最多一小时一次
const PROUD_FILES = 3          // 一轮里改了这么多个文件，她会有点小得意
const EDIT_TOOLS = new Set(['Edit', 'MultiEdit', 'Write', 'NotebookEdit'])

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
  history: [] as Activity[],
  lastNightNote: 0,
  editedFiles: new Set<string>(),   // 这一轮改过的文件
  writing: Promise.resolve() as Promise<void>,
}

// 气泡显示这件事，并记进"最近做了什么"
function show(activity: Activity, remember = true) {
  s.activity = activity
  if (remember) {
    s.history.push(activity)
    if (s.history.length > HISTORY_SIZE) s.history.shift()
  }
}

// 做完了。凌晨的话，顺便说一下现在几点（只说时间，一小时最多一次）
function doneText(now: number) {
  const parts = ['做完啦']
  const edited = s.editedFiles.size
  if (edited >= PROUD_FILES) parts.push(`改了 ${edited} 个文件`)
  const hour = new Date(now).getHours()
  if (hour < 5 && now - s.lastNightNote >= NIGHT_NOTE_EVERY) {
    s.lastNightNote = now
    parts.push(`已经凌晨 ${hour} 点了哦`)
  }
  return parts.join(' · ')
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
  const { mood, since, rateLimits, cost, cwd, file, activity, history } = s
  const text = JSON.stringify({ mood, since, updated: Date.now(), rateLimits, cost, cwd, activity, history })
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
      s.editedFiles.clear()
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
      show({ text: '需要你确认一下', at: Date.now() })
      await refresh($)
    }
    return verdict
  })

  on('tool.call', async ($, e, next) => {
    const isAsking = ASKING_TOOLS.has(e.tool) && e.agentId === undefined
    if (isAsking) s.asking++
    else s.tools++
    const isMain = e.agentId === undefined
    const text = describe(e.tool, e as Record<string, unknown>)
    const activity: Activity | undefined = text ? { text, at: Date.now() } : undefined
    // 帮手（子代理）做的事也显示在气泡里，但"最近做了什么"只记我自己的，免得被刷屏
    if (activity && !(s.asking > 0 && !isAsking)) show(activity, isMain)
    await refresh($)
    let failed = false
    try {
      const ran = await next(e)
      failed = 'isError' in ran && ran.isError === true
      // 记下这一轮真正改成功的文件（被拒绝或出错的不算）
      const input = e as Record<string, unknown>
      const path = input.file_path ?? input.notebook_path
      if (isMain && EDIT_TOOLS.has(e.tool) && !failed && !('deny' in ran) && typeof path === 'string') {
        s.editedFiles.add(path)
      }
      return ran
    } finally {
      const now = Date.now()
      if (activity) {
        activity.end = now
        if (failed) activity.error = true
      }
      // 出错了也让你看见：气泡如实说，她会冒汗
      if (failed && isMain) show({ text: '刚才出错了，我在想办法', at: now, end: now, error: true }, false)
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
      if (e.isAborted) s.activity = undefined
      else show({ text: doneText(now), at: now, end: now, proud: s.editedFiles.size >= PROUD_FILES })
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
