import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { sets } from './sets.mjs'
const dir = fileURLToPath(new URL('../logo-review/', import.meta.url))
const expected = [...readFileSync(new URL('../../web-static/src/icons/paths.ts', import.meta.url),'utf8').matchAll(/^  (?:'([^']+)'|(\w+)): \[/gm)].map(m=>m[1]||m[2]).sort()
for(const [id,set] of Object.entries(sets)){
 if(JSON.stringify(Object.keys(set.icons).sort())!==JSON.stringify(expected))throw Error('Incomplete icon family '+id)
 const symbols=Object.entries(set.icons).map(([name,paths])=>`<symbol id="${name}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${set.stroke}" stroke-linecap="${set.cap}" stroke-linejoin="${set.join}">${paths.map(d=>`<path d="${d}"/>`).join('')}</symbol>`).join('')
 writeFileSync(dir+`assets/icons-direction-${id.toLowerCase()}.svg`,`<svg xmlns="http://www.w3.org/2000/svg"><defs>${symbols}</defs></svg>`)
}
const template=readFileSync(new URL('./page.html',import.meta.url),'utf8')
writeFileSync(dir+'icon-directions.html',template.replace('/* ICON_DATA */',`const sets=${JSON.stringify(sets)};`))
console.log('Two complete 46-icon families generated')
