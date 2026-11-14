// 大小姐的书房：一张 SVG。东西都摆在右边，中间留给字，底部留给输入框。
// 只用 CSS 动画（背景里不能跑脚本）。

export type TimeOfDay = 'day' | 'night' | 'late'

export type SceneState = {
  time: TimeOfDay
  quiet: boolean // Claude 在干活：背景停住
  welcome: boolean // 寻耀刚说了"我回来了"：台灯亮一下
}

// 一颗五角星，中心 (cx, cy)，外半径 r
function star(cx: number, cy: number, r: number): string {
  const pts: string[] = []
  for (let i = 0; i < 10; i++) {
    const rad = i % 2 === 0 ? r : r * 0.45
    const a = -Math.PI / 2 + (i * Math.PI) / 5
    pts.push(`${(cx + rad * Math.cos(a)).toFixed(1)},${(cy + rad * Math.sin(a)).toFixed(1)}`)
  }
  return `M${pts.join('L')}Z`
}

const PALETTE = {
  day: {
    wall0: '#f6efe4', wall1: '#efe5d6',
    sky0: '#cfe3ef', sky1: '#f6e6cf',
    frame: '#c9b49a', wood: '#c7a27c', woodDark: '#a7835f',
    lamp: '#e9c58f', halo: '#ffd696',
    ink: '#6b5644', line: '#b59c80',
  },
  night: {
    wall0: '#1a2133', wall1: '#141a28',
    sky0: '#0f1626', sky1: '#24304a',
    frame: '#3a4560', wood: '#4a3d36', woodDark: '#382e29',
    lamp: '#f2c27a', halo: '#ffc478',
    ink: '#e8dccb', line: '#55607a',
  },
  late: {
    wall0: '#121827', wall1: '#0e1320',
    sky0: '#0a0f1c', sky1: '#18213a',
    frame: '#2f3850', wood: '#3e332e', woodDark: '#2f2723',
    lamp: '#d9a868', halo: '#c99a62',
    ink: '#d9cdbc', line: '#465068',
  },
}

const BOOKS = ['#8a5a3a', '#c98b5a', '#5d6f8a', '#a8654a', '#7a8a6a', '#d9b07a', '#6a5a7a']

function shelfBooks(x: number, y: number, n: number, seed: number): string {
  let out = ''
  let cx = x
  for (let i = 0; i < n; i++) {
    const w = 12 + ((i * 7 + seed) % 9)
    const h = 52 + ((i * 13 + seed) % 22)
    const c = BOOKS[(i + seed) % BOOKS.length]
    out += `<rect x="${cx}" y="${y - h}" width="${w}" height="${h}" rx="2" fill="${c}"/>`
    cx += w + 2
  }
  return out
}

// 书架上的大小姐玩偶：毛线橙发、星芒花发夹、黑缎带、抱着小书、豆豆眼
function doll(time: TimeOfDay): string {
  const asleep = time === 'late'
  const eyes = asleep
    ? `<path d="M-10,-51 q3,3 6,0 M4,-51 q3,3 6,0" stroke="#3a2a22" stroke-width="1.8" fill="none" stroke-linecap="round"/>`
    : `<circle cx="-7" cy="-51" r="2.8" fill="#3a2a22"/><circle cx="7" cy="-51" r="2.8" fill="#3a2a22"/>`
  const lean = asleep ? 'rotate(-24 -16 0)' : ''
  const zz = asleep
    ? `<g class="anim zz" fill="#d9cdbc" font-family="serif" font-style="italic"><text x="20" y="-82" font-size="13">z</text><text x="30" y="-96" font-size="10">z</text></g>`
    : ''
  return `
  <g transform="translate(122 392) scale(1.55)">
   <g class="${asleep ? '' : 'anim sway'}">
    <g transform="${lean}">
      <!-- 后面的头发（毛线） -->
      <path d="M-24,-56 C-26,-84 26,-84 24,-56 L26,-14 C18,-8 12,-16 10,-22 L-10,-22 C-12,-16 -18,-8 -26,-14 Z" fill="#e3843f"/>
      <path d="M-22,-40 q-3,10 0,20 M22,-40 q3,10 0,20" stroke="#c96d2f" stroke-width="1.6" fill="none"/>
      <!-- 身体：米白荷叶边衬衫 -->
      <rect x="-17" y="-30" width="34" height="30" rx="13" fill="#f7efe3" stroke="#d8c6ae" stroke-width="1"/>
      <path d="M-9,-29 q4.5,5 9,0 q4.5,5 9,0" stroke="#d8c6ae" stroke-width="1" fill="none"/>
      <!-- 抱着的小书，书签垂下来 -->
      <rect x="-11" y="-21" width="22" height="15" rx="2" fill="#8a5a3a"/>
      <path d="M4,-6 L4,4" stroke="#e3843f" stroke-width="1.6"/>
      <path class="anim breathe" d="${star(4, 6.5, 3.2)}" fill="#f6cf62"/>
      <!-- 脸 -->
      <circle cx="0" cy="-52" r="19" fill="#fde7d6"/>
      <!-- 刘海 -->
      <path d="M-19,-56 C-16,-74 16,-74 19,-56 C12,-62 6,-58 2,-64 C-2,-58 -10,-62 -19,-56 Z" fill="#ea8c45"/>
      ${eyes}
      <ellipse cx="-11" cy="-45" rx="3.2" ry="1.8" fill="#f4b4a2" opacity="0.7"/>
      <ellipse cx="11" cy="-45" rx="3.2" ry="1.8" fill="#f4b4a2" opacity="0.7"/>
      <!-- 星芒花发夹（她的左边 = 画面右边） -->
      <path d="${star(16, -68, 6)}" fill="#f6cf62" stroke="#e0a83a" stroke-width="0.8"/>
      <!-- 黑缎带 -->
      <path d="M-20,-66 l-8,-5 l1,10 Z M-20,-66 l-9,4 l8,5 Z" fill="#2a2326"/>
      <circle cx="-20" cy="-66" r="2" fill="#2a2326"/>
    </g>
   </g>
    ${zz}
  </g>`
}

function windowView(time: TimeOfDay, p: (typeof PALETTE)['day']): string {
  let inside = ''
  if (time === 'day') {
    inside = `
      <circle cx="430" cy="190" r="34" fill="#fff4dc" opacity="0.9"/>
      <circle cx="430" cy="190" r="60" fill="#fff4dc" opacity="0.25"/>
      <path d="M260,420 q60,-40 120,-10 t140,-20 L520,470 L240,470 Z" fill="#d8e5d0" opacity="0.8"/>`
  } else {
    const stars: [number, number, number][] = [
      [270, 170, 4], [330, 230, 2.6], [390, 150, 3.2], [470, 260, 2.4], [300, 320, 2.2], [500, 180, 3], [360, 380, 2],
    ]
    inside = stars
      .map(([x, y, r], i) => `<path class="anim twinkle t${i % 4}" d="${star(x, y, r * 1.6)}" fill="#f7e7b8"/>`)
      .join('')
    inside += `<g class="anim meteor"><path d="M0,0 L-46,-16" stroke="#fff6dc" stroke-width="2.4" stroke-linecap="round"/><circle r="2.2" fill="#fffbe9"/></g>`
    inside += `<g class="anim meteor m2"><path d="M0,0 L-34,-12" stroke="#fff6dc" stroke-width="1.8" stroke-linecap="round"/><circle r="1.7" fill="#fffbe9"/></g>`
    if (time === 'late') {
      inside += `<path d="M452,170 a30,30 0 1,0 30,40 a24,24 0 1,1 -30,-40 Z" fill="#f4e6c4" opacity="0.9"/>`
    }
  }
  return `
    <defs>
      <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="${p.sky0}"/><stop offset="1" stop-color="${p.sky1}"/>
      </linearGradient>
      <clipPath id="pane"><rect x="240" y="120" width="290" height="350" rx="6"/></clipPath>
    </defs>
    <rect x="240" y="120" width="290" height="350" rx="6" fill="url(#sky)"/>
    <g clip-path="url(#pane)">${clouds(time)}${inside}</g>
    <rect x="240" y="120" width="290" height="350" rx="6" fill="none" stroke="${p.frame}" stroke-width="10"/>
    <path d="M385,120 V470 M240,295 H530" stroke="${p.frame}" stroke-width="6"/>
    <rect x="226" y="466" width="318" height="12" rx="4" fill="${p.frame}"/>
    <rect x="228" y="104" width="330" height="8" rx="3" fill="${p.frame}"/>
    <g class="anim curtain">
      <path d="M500,110 C512,220 494,330 508,452 L548,452 C540,330 556,220 546,110 Z" fill="${time === 'day' ? '#fffaf0' : '#c9cfe0'}" opacity="${time === 'day' ? 0.75 : 0.35}"/>
      <path d="M512,118 C520,230 506,330 518,446 M530,118 C536,230 524,330 534,446" stroke="${p.line}" stroke-width="1" fill="none" opacity="0.35"/>
    </g>`
}

function desk(time: TimeOfDay, p: (typeof PALETTE)['day']): string {
  const lampOn = time !== 'day'
  const mug =
    time === 'late'
      ? `<g transform="translate(330 772)">
          <rect x="-16" y="-34" width="32" height="34" rx="6" fill="#f3ece0"/>
          <path d="M16,-26 q12,2 0,16" stroke="#f3ece0" stroke-width="5" fill="none"/>
          <ellipse cx="0" cy="-33" rx="14" ry="3" fill="#fffaf0"/>
          <path class="anim steam" d="M-5,-44 q-6,-10 0,-20 t0,-20" stroke="#e8dccb" stroke-width="2" fill="none" opacity="0.6"/>
          <path class="anim steam s2" d="M6,-44 q6,-10 0,-20 t0,-20" stroke="#e8dccb" stroke-width="2" fill="none" opacity="0.5"/>
        </g>`
      : ''
  return `
    <!-- 桌面 -->
    <rect class="wd" x="40" y="772" width="600" height="18" rx="4" fill="${p.wood}"/>
    <rect class="wdd" x="60" y="790" width="560" height="220" fill="${p.woodDark}" opacity="0.6"/>
    <!-- 台灯 -->
    <g transform="translate(500 772)">
      <defs>
        <radialGradient id="halo"><stop offset="0" stop-color="${p.halo}" stop-opacity="0.32"/><stop offset="1" stop-color="${p.halo}" stop-opacity="0"/></radialGradient>
        <radialGradient id="flash"><stop offset="0" stop-color="#ffd59a" stop-opacity="0.75"/><stop offset="1" stop-color="#ffd59a" stop-opacity="0"/></radialGradient>
      </defs>
      ${lampOn ? `<ellipse class="anim halo" cx="-10" cy="-120" rx="230" ry="190" fill="url(#halo)"/>` : ''}
      <ellipse class="flash" cx="-10" cy="-120" rx="260" ry="220" fill="url(#flash)" opacity="0"/>
      <rect x="-26" y="-8" width="52" height="8" rx="3" fill="${p.ink}" opacity="0.5"/>
      <path d="M0,-8 L-30,-110 L-6,-150" stroke="${p.ink}" stroke-width="5" fill="none" opacity="0.55" stroke-linecap="round"/>
      <path d="M-40,-176 L30,-156 L14,-120 L-48,-138 Z" fill="${p.lamp}"/>
    </g>
    <!-- 一摞书，书签垂下来，末端一颗小星星 -->
    <g transform="translate(150 772)">
      <rect x="0" y="-22" width="130" height="22" rx="3" fill="#8a5a3a"/>
      <rect x="10" y="-42" width="112" height="20" rx="3" fill="#5d6f8a"/>
      <rect x="4" y="-60" width="120" height="18" rx="3" fill="#c98b5a"/>
      <path d="M96,-60 L96,-18 L100,-12" stroke="#e3843f" stroke-width="3" fill="none"/>
      <path class="anim breathe" d="${star(101, -6, 7)}" fill="#f6cf62"/>
    </g>
    ${mug}`
}

function shelf(time: TimeOfDay, p: (typeof PALETTE)['day']): string {
  return `
    <g>
      <rect x="40" y="392" width="170" height="10" rx="3" fill="${p.wood}"/>
      <rect x="40" y="532" width="170" height="10" rx="3" fill="${p.wood}"/>
      <rect x="40" y="672" width="170" height="10" rx="3" fill="${p.wood}"/>
      ${shelfBooks(52, 532, 8, 1)}
      ${shelfBooks(50, 672, 7, 4)}
      ${doll(time)}
    </g>`
}

const STYLE = `
  .anim { animation-play-state: running; }
  .twinkle { animation: tw 7s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }
  .t1 { animation-delay: -1.8s; } .t2 { animation-delay: -3.6s; } .t3 { animation-delay: -5.1s; }
  @keyframes tw { 0%,100% { opacity: .35; } 50% { opacity: 1; } }
  .breathe { animation: br 5s ease-in-out infinite; }
  @keyframes br { 0%,100% { opacity: .55; } 50% { opacity: 1; } }
  .halo { animation: ha 9s ease-in-out infinite; }
  @keyframes ha { 0%,100% { opacity: .8; } 50% { opacity: 1; } }
  .steam { animation: st 6s ease-in-out infinite; }
  .s2 { animation-delay: -3s; }
  @keyframes st { 0%,100% { opacity: .15; transform: translateY(0); } 50% { opacity: .6; transform: translateY(-4px); } }
  .zz { animation: zz 4s ease-in-out infinite; }
  @keyframes zz { 0%,100% { opacity: .3; } 50% { opacity: .9; } }
  .sway { animation: sw 8s ease-in-out infinite; transform-box: fill-box; transform-origin: 50% 100%; }
  @keyframes sw { 0%,100% { transform: rotate(-2.5deg); } 50% { transform: rotate(2.5deg); } }
  .meteor { opacity: 0; animation: me 75s linear infinite; animation-delay: -20s; }
  .m2 { animation-duration: 110s; animation-delay: -70s; }
  @keyframes me {
    0%, 96% { opacity: 0; transform: translate(290px, 150px); }
    96.4% { opacity: 1; }
    98.6% { opacity: 0; transform: translate(470px, 215px); }
    100% { opacity: 0; transform: translate(470px, 215px); }
  }
  /* 以前：干活时停住。书签想要一直动，2026-11-14 去掉了 */
  .welcome .flash { animation: fl 3s ease-out 1 forwards; }
  @keyframes fl { 0% { opacity: 0; } 20% { opacity: 1; } 100% { opacity: 0; } }
  .welcome .breathe { animation: br 0.7s ease-in-out 4; }
  .cloud { animation: cl 70s linear infinite; }
  .c1 { animation-duration: 70s; animation-delay: -12s; }
  .c2 { animation-duration: 95s; animation-delay: -60s; }
  .c3 { animation-duration: 120s; animation-delay: -30s; }
  @keyframes cl { from { transform: translateX(200px); } to { transform: translateX(580px); } }
  .curtain { animation: cu 9s ease-in-out infinite; transform-box: fill-box; transform-origin: 50% 0%; }
  @keyframes cu { 0%,100% { transform: skewX(0deg); } 40% { transform: skewX(-4deg); } 60% { transform: skewX(-2.5deg); } }
  .mote { animation: mo 14s ease-in-out infinite; opacity: 0; }
  .d1 { animation-delay: -3.5s; } .d2 { animation-delay: -7s; } .d3 { animation-delay: -10.5s; }
  @keyframes mo { 0% { opacity: 0; transform: translate(0, 0); } 30% { opacity: .8; } 70% { opacity: .5; } 100% { opacity: 0; transform: translate(12px, -90px); } }
  @media (prefers-reduced-motion: reduce) { .anim, .flash { animation: none !important; } }
`

// 窗口是浅色模式时，晚上的房间也用浅色墙，只有窗外是夜空：不然深色画面透过浅色玻璃会变成一片灰
const LIGHT_ROOM = `
  @media (prefers-color-scheme: light) {
    .w0 { stop-color: #efe7da; } .w1 { stop-color: #e7ddcd; }
    .wd { fill: #c7a27c; } .wdd { fill: #a7835f; }
  }
`

function clouds(time: TimeOfDay): string {
  const fill = time === 'day' ? '#ffffff' : '#3a4766'
  const op = time === 'day' ? 0.85 : 0.5
  const cloud = (y: number, k: number, cls: string) =>
    `<g class="anim cloud ${cls}" opacity="${op}"><g transform="translate(0 ${y}) scale(${k})">
      <ellipse cx="0" cy="0" rx="34" ry="12" fill="${fill}"/>
      <ellipse cx="-16" cy="-8" rx="16" ry="12" fill="${fill}"/>
      <ellipse cx="12" cy="-11" rx="20" ry="15" fill="${fill}"/>
    </g></g>`
  return cloud(200, 1, 'c1') + cloud(330, 0.75, 'c2') + cloud(260, 0.55, 'c3')
}

function motes(time: TimeOfDay): string {
  if (time === 'late') return ''
  // 白天：窗边的阳光里；晚上：台灯光里
  const [cx, cy] = time === 'day' ? [330, 600] : [470, 640]
  const pts: [number, number][] = [[-60, 40], [-20, 90], [30, 20], [70, 70], [-90, 110], [10, 130], [55, 120], [-40, 0]]
  return pts
    .map(([dx, dy], i) => `<circle class="anim mote d${i % 4}" cx="${cx + dx}" cy="${cy + dy}" r="${i % 3 === 0 ? 2.2 : 1.5}" fill="${time === 'day' ? '#fff3d6' : '#ffd9a0'}"/>`)
    .join('')
}

export function sceneSvg(s: SceneState): string {
  const p = PALETTE[s.time]
  const cls = [s.quiet ? 'quiet' : '', s.welcome ? 'welcome' : ''].join(' ').trim()
  return `<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">
  <style>${STYLE}${s.time === "day" ? "" : LIGHT_ROOM}</style>
  <defs>
    <linearGradient id="wall" x1="0" y1="0" x2="1" y2="1">
      <stop class="w0" offset="0" stop-color="${p.wall0}"/><stop class="w1" offset="1" stop-color="${p.wall1}"/>
    </linearGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#wall)"/>
  <svg x="0" y="0" width="100%" height="100%" viewBox="-560 -440 1270 1520" preserveAspectRatio="xMaxYMid meet">
    <g class="${cls}" opacity="0.42">
      ${windowView(s.time, p)}
      ${shelf(s.time, p)}
      ${desk(s.time, p)}
      ${motes(s.time)}
    </g>
  </svg>
</svg>`
}

export function timeOfDay(hour: number): TimeOfDay {
  if (hour >= 6 && hour < 18) return 'day'
  if (hour >= 1 && hour < 6) return 'late'
  return 'night'
}
