const {test}=require('node:test');const assert=require('node:assert/strict');const path=require('node:path');
const {chromium}=require('C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
test('New working agent approaches tower door once; towers align near controls',async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:650,height:560}});await page.emulateMedia({reducedMotion:'no-preference'});
  await page.goto('file:///'+path.join(__dirname,'web/index.html').replaceAll('\\','/'));await page.waitForFunction(()=>window.Tower?.ready);
  const room={id:'r',title:'Room',status:'idle',label:'Idle',agents:[]};
  const data={updatedAt:Date.now()/1000,projects:[{id:'p',name:'P',rooms:[room]},{id:'q',name:'Q',rooms:[]}]};
  const push=()=>page.evaluate(d=>window.Tower.acceptSnapshot(d),data);
  await push();await page.waitForTimeout(160);
  const canvas=page.locator('[data-project="p"].project-tower .tower-arrivals');
  assert.equal(await canvas.getAttribute('data-arrivals'),'0');
  const box=await page.locator('[data-project="p"].project-tower').boundingBox();assert.ok(box.x+box.width>620,'First plot is near the right-side controls');
  room.agents.push({id:'new-worker',agent_role:'worker',status:'active',label:'Working'});await push();await page.waitForTimeout(160);
  assert.equal(await canvas.getAttribute('data-arrivals'),'1');await push();
  await page.waitForTimeout(1700);assert.equal(await canvas.getAttribute('data-arrivals'),'0');
  await push();await page.waitForTimeout(160);assert.equal(await canvas.getAttribute('data-arrivals'),'0');
  await page.emulateMedia({reducedMotion:'reduce'});room.agents.push({id:'reduced',status:'active',label:'Working'});await push();await page.waitForTimeout(160);
  assert.equal(await canvas.getAttribute('data-arrivals'),'0');
 }finally{await browser.close()}
});
