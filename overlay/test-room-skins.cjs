const {test}=require('node:test');const assert=require('node:assert/strict');
const {chromium}=require('C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const path=require('node:path');
test('Complete scene variants are stable during visits and refresh size only on entry',async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:650,height:450}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('file:///'+path.join(__dirname,'web/index.html').replaceAll('\\','/'));
  await page.waitForFunction(()=>window.Tower?.ready);
  const room={id:'skin-session',title:'Scene',status:'idle',label:'Waiting',agents:[]};
  const data={updatedAt:Date.now()/1000,projects:[{id:'p',name:'Project',rooms:[room]}]};
  const push=()=>page.evaluate(d=>window.Tower.acceptSnapshot(d),data);
  await push();await page.locator('.overview-floor').click();
  const initial=await page.locator('.scene').getAttribute('data-skin-id');
  assert.match(initial,/^cabinet-[012]$/);
  room.agents=Array.from({length:22},(_,i)=>({id:String(i),agent_role:'worker',status:'idle',label:'Waiting'}));
  await push();assert.equal(await page.locator('.scene').getAttribute('data-skin-id'),initial);
  assert.equal(await page.locator('.employee-marker').count(),23);
  await page.locator('#back-icon').click();await page.locator('.overview-floor').click();
  const large=await page.locator('.scene').getAttribute('data-skin-id');assert.match(large,/^wings-[012]$/);
  assert.equal(initial.at(-1),large.at(-1),'Session retains its variant');
  await page.screenshot({path:path.join(__dirname,'runtime/unified-scene-preview.png'),omitBackground:true});
  for(const [count,tier] of [[4,'cabinet'],[8,'workshop'],[16,'hall'],[23,'wings']]){
   await page.locator('#back-icon').click();room.agents=room.agents.slice(0,count-1);
   while(room.agents.length<count-1)room.agents.push({id:String(room.agents.length),status:'idle',label:'Waiting'});
   await push();await page.locator('.overview-floor').click();
   assert.equal(await page.locator('.scene').getAttribute('data-skin'),tier);
   assert.equal(await page.locator('.employee-marker').count(),count);
  }
  assert.deepEqual(errors,[]);
 }finally{await browser.close()}
});
