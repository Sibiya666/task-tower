const {test}=require('node:test');const assert=require('node:assert/strict');const path=require('node:path');
const {chromium}=require('C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
test('World controls, compact real floors, weather, hiding and revival work together',async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:820,height:560}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.emulateMedia({reducedMotion:'reduce'});
  await page.goto('file:///'+path.join(__dirname,'web/index.html').replaceAll('\\','/'));await page.waitForFunction(()=>window.Tower?.ready);
  const old=Date.now()/1000-2000;
  const data={updatedAt:Date.now()/1000,projects:[
   {id:'live',name:'Main',rooms:[{id:'live-room',title:'Work',status:'active',label:'Работает',agents:[]}]},
   {id:'long',name:'Dialoid',rooms:Array.from({length:16},(_,i)=>({id:'floor-'+String(i).padStart(2,'0'),title:'Floor '+(i+1),status:i===15?'waiting':'completed',lastEvent:old,label:i===15?'Ждёт решения':'Завершил',agents:[]}))},
   {id:'sleeping',name:'Idle',rooms:[{id:'sleep',status:'completed',lastEvent:old,label:'Завершил',agents:[]}]}
  ]};
  const push=()=>page.evaluate(d=>window.Tower.acceptSnapshot(d),data);await push();
  const long=page.locator('.project-tower[data-project="long"]'),sleeping=page.locator('.project-tower[data-project="sleeping"]');
  assert.equal(await long.getAttribute('data-floor-count'),'16');assert.equal(await long.getAttribute('data-detail-levels'),'4');assert.equal(await long.locator('.overview-floor').count(),16);assert.equal(await sleeping.isVisible(),false);
  await long.locator('.tower-capacity').click();await page.locator('#world-menu button').filter({hasText:'16 · Floor 16'}).click();assert.equal(await page.locator('.session-floor').getAttribute('data-session'),'floor-15');await page.locator('#back-icon').click();
  await page.mouse.click(15,15,{button:'right'});assert.equal(await page.locator('#world-menu').isVisible(),true);
  await page.locator('[data-setting="mode"]').selectOption('day');await page.locator('[data-setting="weather"]').selectOption('clouds');await page.keyboard.press('Escape');await page.waitForTimeout(250);
  assert.equal(await page.locator('#world-sky').getAttribute('data-phase'),'day');
  assert.equal(await page.locator('#world-menu').isVisible(),false);assert.equal(await page.locator('html').evaluate(e=>getComputedStyle(e).getPropertyValue('--world-brightness')),'1.12');
  await page.screenshot({path:path.join(__dirname,'runtime/world-day-clouds.png'),omitBackground:true});
  await page.mouse.click(15,15,{button:'right'});await page.locator('[data-setting="mode"]').selectOption('night');await page.locator('[data-setting="weather"]').selectOption('rain');await page.keyboard.press('Escape');await page.waitForTimeout(250);
  await page.screenshot({path:path.join(__dirname,'runtime/world-night-rain.png'),omitBackground:true});
  assert.equal(await page.locator('#world-sky').getAttribute('data-phase'),'night');await page.mouse.click(15,15,{button:'right'});assert.match(await page.locator('#world-time-status').textContent(),/Ночь.*ручной режим/);await page.keyboard.press('Escape');
  data.projects[2].rooms[0].status='active';await push();assert.equal(await sleeping.isVisible(),true);
  data.updatedAt=1;data.projects[0].rooms[0].status='completed';data.projects[0].rooms[0].lastEvent=old;await push();assert.equal(await page.locator('.project-tower[data-project="live"]').isVisible(),true);
  assert.deepEqual(errors,[]);
 }finally{await browser.close()}
});
