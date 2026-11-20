// Targeted lifecycle test: execute the page's actual ref/effect and timer code.
// No React rendering, API, model, or database is involved.
const fs = require('node:fs')
const vm = require('node:vm')
const assert = require('node:assert/strict')
const path = require('node:path')
const delay = ms => new Promise(r => setTimeout(r, ms))
const file = process.argv[2] || path.join(__dirname, '../app/[lng]/(newLayout)/workspaces/[id]/WorkspaceDetailPage.tsx')
const source = fs.readFileSync(file, 'utf8')
function page() {
 const refs = source.slice(source.indexOf('  const askAbortControllerRef ='), source.indexOf('  // 获取数据源列表'))
 let fn = source.slice(source.indexOf('  const askSmoothProgressTo ='), source.indexOf('  // 执行问数查询：'))
 assert(refs && fn.includes('}, stepDuration)'))
 const hooks=[], updates=[]
 const context = { window:{}, setInterval, clearInterval, useRef:current=>({current}),
   useEffect:fn=>hooks.push(fn), updateAskProgress:v=>updates.push(v) }
 vm.createContext(context)
 const js = (refs+fn).replace(/useRef<[^>]+>/g,'useRef')
   .replace('(targetPercent: number, duration: number)', '(targetPercent, duration)')
   .replace('new Promise<void>', 'new Promise')
 vm.runInContext(js+'\nthis.run=askSmoothProgressTo;this.timer=askProgressIntervalRef;this.cancel=askCancelFlagRef',context)
 let cleanups=hooks.map(fn=>fn())
 return {updates,run:context.run,timer:context.timer,cancel:context.cancel,
   unmount:()=>cleanups.forEach(fn=>fn?.()),
   remount:()=>{cleanups=hooks.map(fn=>fn())}}
}
async function main() {
 let p=page(); await p.run(80,100)
 assert.equal(p.updates.length,20); assert.equal(p.updates.at(-1),80); assert.equal(p.timer.current,null)
 console.log('PASS normal interpolation')
 p=page(); await p.run(80,0); assert.deepEqual(p.updates,[80])
 console.log('PASS immediate progress')
 p=page(); const pending=p.run(80,100); p.cancel.current=true; await pending
 assert.equal(p.updates.length,0); assert.equal(p.timer.current,null)
 console.log('PASS cancellation')
 p=page(); p.run(80,100); p.unmount(); const count=p.updates.length
 await delay(140); assert.equal(p.updates.length,count,'progress must stop on unmount')
 assert.equal(p.timer.current,null)
 console.log('PASS unmount stops active interval')
 await p.run(100,0); await p.run(100,100)
 assert.equal(p.updates.length,count); assert.equal(p.timer.current,null)
 console.log('PASS no progress/timer creation after unmount')
 p.remount(); await p.run(80,100)
 assert.equal(p.updates.at(-1),80); p.unmount()
 console.log('PASS effect cleanup/setup replay')
}
main().catch(e=>{console.error(e);process.exitCode=1})
