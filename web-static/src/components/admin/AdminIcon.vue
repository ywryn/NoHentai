<script setup>
defineProps({ name: String, size: { type: Number, default: 20 } })
const paths = {
  grid: ['M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z'],
  gallery: ['M4 3h16a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z', 'm3 16 5-5 4 4 4-6 5 7', 'M8 7h.01'],
  book: ['M4 19.5A2.5 2.5 0 0 1 6.5 17H20M6.5 3H20v19H6.5A2.5 2.5 0 0 1 4 19.5v-14A2.5 2.5 0 0 1 6.5 3Z', 'M9 3v7l2-1 2 1V3'],
  filter: ['M4 5h16M7 12h10M10 19h4', 'M8 3v4M16 10v4M12 17v4'],
  translate: ['M3 5h12M9 3v2M5 5c1 6 5 9 9 10M13 5c-1 6-5 9-9 10', 'm13 21 4-11 4 11M14.5 17h5'],
  tasks: ['M9 6h11M9 12h11M9 18h11M3 6l1 1 2-2M3 12l1 1 2-2M3 18l1 1 2-2'],
  pulse: ['M3 12h4l3-8 4 16 3-8h4'],
  key: ['M15 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z', 'm8 10-5 5v6h4v-3h3v-3l2-2'],
  arrow: ['M7 17 17 7M7 7h10v10'],
  chevron: ['m9 5 7 7-7 7'],
  back: ['m15 18-6-6 6-6'],
  menu: ['M4 6h16M4 12h16M4 18h16'],
  close: ['m6 6 12 12M6 18 18 6'],
  logout: ['M9 4H4v16h5M14 8l4 4-4 4M9 12h12'],
  search: ['M19 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0Zm-2 6 5 5'],
  plus: ['M12 5v14M5 12h14'],
  save: ['M5 3h12l4 4v14H3V3h2Zm2 0v6h10V3M7 21v-8h10v8'],
  refresh: ['M20 7v5h-5M4 17v-5h5', 'M6 7a7 7 0 0 1 12-1l2 3M4 15l2 3a7 7 0 0 0 12-1'],
  clock: ['M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM12 7v5l3 2'],
  check: ['m5 12 4 4L19 6'],
  info: ['M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM12 11v6M12 7h.01'],
  shield: ['m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z', 'm8 12 3 3 5-6'],
  download: ['M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5'],
  dots: ['M5 12h.01M12 12h.01M19 12h.01'],
  trash: ['M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7'],
}
</script>
<template><svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path v-for="(d, i) in paths[name] || paths.grid" :key="i" :d="d" /></svg></template>
