const {test}=require('node:test');const assert=require('node:assert/strict');const path=require('node:path');
const {chromium}=require('C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const sharp=require('C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
async function warm(node){const {data}=await sharp(await node.screenshot()).ensureAlpha().raw().toBuffer({resolveWithObject:true});let n=0;for(let i=0;i<data.length;i+=4)if(data[i]>170&&data[i+1]>120&&data[i+2]<150&&data[i]>data[i+1]*1.15)n++;return n}
test('Renamed session retains its floor and lights up when activity resumes',async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage();await page.goto('file:///'+path.join(__dirname,'web/index.html').replaceAll('\\','/'));await page.waitForFunction(()=>window.Tower?.ready);
  const room={id:'stable-id',title:'Before',status:'idle',label:'Свободен',agents:[]},data={updatedAt:Date.now()/1000,projects:[{id:'p',name:'Project',rooms:[room]}]};
  await page.evaluate(d=>window.Tower.acceptSnapshot(d),data);
  const floor=page.locator('.overview-floor[data-session="stable-id"]'),dark=await warm(floor);
  await floor.evaluate(e=>e.dataset.retained='yes');
  room.title='Renamed';room.status='active';room.label='Работает';await page.evaluate(d=>window.Tower.acceptSnapshot(d),data);
  assert.equal(await floor.getAttribute('data-retained'),'yes');assert.equal(await floor.getAttribute('data-active-count'),'1');
  assert.match(await floor.getAttribute('title'),/Renamed/);assert.ok(await warm(floor)>dark+5);
 }finally{await browser.close()}
});
