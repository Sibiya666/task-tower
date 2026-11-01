const {test}=require('node:test');const assert=require('node:assert/strict');const path=require('node:path');
const {chromium}=require('C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
test('Overview scroll survives entering, moving through a compact viewport, updates and return',async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:650,height:560}});
  await page.goto('file:///'+path.join(__dirname,'web/index.html').replaceAll('\\','/'));await page.waitForFunction(()=>window.Tower?.ready);
  const data={updatedAt:Date.now()/1000,projects:Array.from({length:12},(_,i)=>({id:'p'+i,name:'P'+i,rooms:[{id:'r'+i,title:'Room',status:'active',label:'Working',agents:[]}]}))};
  await page.evaluate(d=>window.Tower.acceptSnapshot(d),data);
  const saved=await page.locator('#overview').evaluate(e=>{e.scrollLeft=90;e.scrollTop=470;return {left:e.scrollLeft,top:e.scrollTop}});
  assert.ok(saved.top>0&&saved.left>0);
  await page.locator('.overview-floor[data-session="r4"]').evaluate(e=>e.click());
  await page.setViewportSize({width:340,height:300});await page.evaluate(d=>window.Tower.acceptSnapshot(d),data);
  await page.locator('#back-icon').click();await page.setViewportSize({width:650,height:560});await page.waitForTimeout(150);
  const restored=await page.locator('#overview').evaluate(e=>({left:e.scrollLeft,top:e.scrollTop}));
  assert.deepEqual(restored,saved);
 }finally{await browser.close()}
});
