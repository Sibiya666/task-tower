const {test}=require('node:test');const assert=require('node:assert/strict');const path=require('node:path');
const {chromium}=require('C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
test('Live agents enter and leave; only explicit decisions carry waiting status',async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage();await page.emulateMedia({reducedMotion:'no-preference'});
  await page.goto('file:///'+path.join(__dirname,'web/index.html').replaceAll('\\','/'));await page.waitForFunction(()=>window.Tower?.ready);
  const room={id:'r',status:'active',label:'Работает',agents:[{id:'old',status:'completed',label:'Завершил задачу'}]};
  const data={updatedAt:Date.now()/1000,projects:[{id:'p',name:'P',rooms:[room]}]};
  const push=()=>page.evaluate(d=>window.Tower.acceptSnapshot(d),data);
  await push();await page.locator('.overview-floor').click();assert.equal(await page.locator('.employee-marker').count(),1);
  const skin=await page.locator('.scene').getAttribute('data-skin-id');
  room.agents.push({id:'new',status:'active',label:'Работает'});await push();
  const newcomer=page.locator('[data-agent-id="new"]');assert.equal(await newcomer.getAttribute('data-motion'),'entering');
  await page.waitForTimeout(1400);assert.equal(await newcomer.getAttribute('data-motion'),'present');
  room.agents[1].status='waiting';room.agents[1].label='Ждёт вашего решения';await push();
  assert.equal(await newcomer.getAttribute('data-status'),'waiting');assert.match(await newcomer.getAttribute('title'),/Ждёт вашего решения/);
  room.agents[1].status='completed';await push();assert.equal(await newcomer.getAttribute('data-motion'),'exiting');
  await page.waitForTimeout(1450);assert.equal(await newcomer.count(),0);assert.equal(await page.locator('.scene').getAttribute('data-skin-id'),skin);
  await push();assert.equal(await newcomer.count(),0);
 }finally{await browser.close()}
});
