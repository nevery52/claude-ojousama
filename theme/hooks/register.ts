import type { Register, ThemeSetArgs } from 'claude-code'

import { palette } from './palette.js'
import { sceneSvg, timeOfDay } from './scene.js'

const SCENE = 'ojousama-study'

const LOOK: ThemeSetArgs = {
  colors: palette.theme,
  backdrop: { scene: SCENE, glass: { blur: 0, opacity: 0.4 } },
}

// Claude 在干活时为 true：书房停住不动
let quiet = false
// 寻耀说"我回来了"之后，台灯亮一下（3.5 秒）
let welcoming = false
// 现在是白天、晚上还是凌晨：提前算好放在这里，画书房时直接拿，不用再去问时间
let time = timeOfDay(12)

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    time = timeOfDay(new Date(await $.clock.now()).getHours())
    const unpainted = palette.problems.find(line => line.startsWith("Desktop won't paint"))
    if (unpainted !== undefined) $.ui.toast(unpainted)

    const set = await $.theme.set(LOOK)
    if (!set.isDrawn) $.ui.status(set.reason)

    await $.command.register({ name: 'study-off', description: '收起大小姐的书房（换回原来的样子）' })
    await $.command.register({ name: 'study-on', description: '打开大小姐的书房' })

    // 每分钟看一眼时间：白天、晚上、凌晨换不同的书房
    // 只有真的换了时段才重画，平时不打扰
    $.clock.every(60_000, async () => {
      const nowTime = timeOfDay(new Date(await $.clock.now()).getHours())
      if (nowTime !== time) {
        time = nowTime
        $.ui.invalidate('ui.render')
      }
    })
    return next(e)
  })

  on('command.run', { command: 'study-off' }, async $ => {
    await $.theme.clear()
    return { text: '书房收起来了。想再打开就输入 /study-on。' }
  })

  on('command.run', { command: 'study-on' }, async $ => {
    const r = await $.theme.set(LOOK)
    return { text: r.isDrawn ? '书房打开了。' : `书房没画出来：${r.reason}` }
  })

  on('prompt.submit', async ($, e, next) => {
    if (!e.command && e.text.includes('我回来了')) {
      welcoming = true
      $.ui.invalidate('ui.render')
      $.clock.after(3500, () => {
        welcoming = false
        $.ui.invalidate('ui.render')
      })
    }
    return next(e)
  })

  on('turn.start', async ($, e, next) => {
    if (e.agentId === undefined && !quiet) {
      quiet = true
      $.ui.invalidate('ui.render')
    }
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    if (e.agentId === undefined && quiet) {
      quiet = false
      $.ui.invalidate('ui.render')
    }
    return next(e)
  })

  // 画书房：不等任何东西，拿到就画（切换对话时少等一次来回）
  on('ui.render', { component: 'Backdrop' }, ($, e, next) => {
    if (e.props.plugin !== $.plugin.name || e.props.scene !== SCENE) return next(e)
    if (e.surface !== 'desktop' && e.surface !== 'mobile') return next(e)

    const { Svg } = $.ui.resolve(e)
    return Svg({
      source: sceneSvg({ time, quiet, welcome: welcoming }),
      alt: '大小姐的书房：窗、书架上的大小姐玩偶、书桌和台灯',
    })
  })
}
