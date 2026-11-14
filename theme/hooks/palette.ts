import { makeColors } from './make-colors.js'

// 大小姐的书房：白天是米白的纸，晚上是墨蓝的夜。点缀用橙色（头发和书签）。
export const palette = makeColors({
  label: 'Ojousama study',
  roles: { accent: '#d9773a', danger: '#b8443a', success: '#5a8a4a', warning: '#c08a2a', pro: '#7a5a9a' },
  light: {
    gray: {
      anchors: {
        'surface-0': '#f1e9dc',
        'surface-1': '#f5eee3',
        'surface-2': '#faf6ef',
        'text-primary': '#2e241d',
        'text-secondary': '#55463a',
        'text-muted': '#6b5c4f',
      },
    },
  },
  dark: {
    gray: {
      anchors: {
        'surface-0': '#141925',
        'surface-1': '#191f2d',
        'surface-2': '#1e2535',
        'surface-3': '#222a3b',
        'text-primary': '#f2ebe0',
        'text-secondary': '#d0c7b9',
        'text-muted': '#aaa194',
      },
    },
  },
})
