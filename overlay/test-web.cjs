const {test}=require('node:test');
const assert=require('node:assert/strict');
const {chromium}=require('C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const path=require('node:path');
const sharp=require('C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
async function warmPixels(locator){const {data}=await sharp(await locator.screenshot()).ensureAlpha().raw().toBuffer({resolveWithObject:true});let n=0;for(let i=0;i<data.length;i+=4)if(data[i]>170&&data[i+1]>120&&data[i+2]<150&&data[i]>data[i+1]*1.15)n++;return n}
const sample={updatedAt:Date.now()/1000,projects:[{id:'p',name:'Dialoid',rooms:[
{id:'a',title:'Короткая сессия',status:'idle',label:'Ожидает задачи',agents:[{id:'child',agent_nickname:'Маг',status:'active',label:'Работает'}]},
{id:'b',title:'Очень длинное название сессии '.repeat(12),status:'error',label:'Ошибка',agents:[]},
{id:'c',title:'Проверка',status:'unknown',label:'Статус неизвестен',agents:[]}]},
{id:'second',name:'Визуализация',rooms:[{id:'s',title:'Башня',status:'idle',label:'Ожидает задачи',agents:[]}]}]};
test('Each project has its own tower, session floors and truthful activity lights',async()=>{
const browser=await chromium.launch({headless:true,channel:'msedge'});
try{
const page=await browser.newPage({viewport:{width:650,height:560}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.emulateMedia({reducedMotion:'no-preference'});
await page.addInitScript(()=>{window._bridgeActions=[];window.chrome=window.chrome||{};window.chrome.webview={postMessage:m=>window._bridgeActions.push(m.action),addEventListener:()=>{}}});
await page.goto('file:///'+path.join(__dirname,'web/index.html').replaceAll('\\','/'));await page.waitForFunction(()=>window.Tower?.ready);
await page.evaluate(data=>window.Tower.acceptSnapshot(data),sample);
assert.equal(await page.locator('.project-tower').count(),2);
assert.equal(await page.locator('.tower-art-canvas').count(),2,'Each tower must render on one canvas');
assert.equal(await page.locator('#details').isVisible(),false,'Overview must not show a details panel');
assert.equal(await page.locator('.legend').isVisible(),false,'Overview must not show a legend');
assert.equal(await page.locator('#titlebar > span').isVisible(),false,'Overview must not show a title');
assert.equal(await page.locator('#collapse').isVisible(),false,'Only pin and close remain');
assert.equal(await page.locator('#pin').isVisible(),true);assert.equal(await page.locator('#close').isVisible(),true);
assert.equal(await page.locator('body').evaluate(el=>getComputedStyle(el).backgroundColor),'rgba(0, 0, 0, 0)','Overview background must be transparent');
assert.equal(await page.locator('.project-tower-name').first().isVisible(),false,'No persistent project labels');
assert.equal(await page.locator('.project-tower[data-project="p"] .overview-floor').count(),3);
assert.equal(await page.locator('.project-tower[data-project="second"] .overview-floor').count(),1);
assert.equal(await page.locator('.overview-floor.is-active').count(),1);
assert.equal(await page.locator('.overview-floor.is-active').getAttribute('data-session'),'a');
await page.locator('.project-tower[data-project="p"] .tower-art-canvas').evaluate(el=>el.dataset.retained='yes');
const originalTower=await page.locator('.project-tower[data-project="p"]').boundingBox();
await page.evaluate(data=>window.Tower.acceptSnapshot(data),sample);
assert.equal(await page.locator('.project-tower[data-project="p"] .tower-art-canvas').getAttribute('data-retained'),'yes','Status refresh must preserve existing canvases');
const expanded=structuredClone(sample);for(let i=0;i<3;i++)expanded.projects.push({id:'new-'+i,name:'Новый проект '+i,rooms:[]});
await page.evaluate(data=>window.Tower.acceptSnapshot(data),expanded);
assert.deepEqual(await page.locator('.project-tower[data-project="p"]').boundingBox(),originalTower,'Adding projects must not move or shrink existing towers');
const secondRow=await page.locator('.project-tower[data-project="new-1"]').boundingBox();assert.ok(secondRow.y>originalTower.y+originalTower.height,'Projects must occupy multiple rows');
await page.evaluate(data=>window.Tower.acceptSnapshot(data),sample);
const floorTarget=page.locator('.overview-floor[data-session="a"]');
const towerCanvas=page.locator('.project-tower[data-project="p"]');
const brightness=async()=>{const {data:p}=await sharp(await towerCanvas.screenshot()).ensureAlpha().raw().toBuffer({resolveWithObject:true});let sum=0;for(let i=0;i<p.length;i+=4)sum+=p[i]+p[i+1]+p[i+2];return sum};
const beforeHover=await brightness();await floorTarget.hover();
assert.equal(await floorTarget.evaluate(el=>getComputedStyle(el).outlineStyle),'none','No rectangular selection frame');
assert.ok(await brightness()>beforeHover,'Hover should brighten the actual stone texture');
await page.mouse.move(5,45);
const targetBox=await floorTarget.boundingBox();await page.mouse.move(targetBox.x+targetBox.width/2,targetBox.y+targetBox.height/2);await page.mouse.down();await page.mouse.move(targetBox.x+targetBox.width/2+14,targetBox.y+targetBox.height/2+8);await page.mouse.up();
assert.equal(await page.locator('body').evaluate(el=>el.classList.contains('overview-mode')),true,'Dragging a tower must not open its floor');
assert.ok(await page.evaluate(()=>window._bridgeActions.includes('drag')),'Tower scene must request native dragging');
await page.locator('.overview-floor[data-session="a"]').click();
assert.equal(await page.locator('.tower-floor').count(),1,'Interior shows only the selected session floor');
assert.equal(await page.locator('.tower-floor').getAttribute('data-session'),'a');
assert.equal(await page.locator('#back-icon').isVisible(),true,'Interior has a back icon');
await page.setViewportSize({width:340,height:300});
assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth||document.documentElement.scrollHeight>innerHeight),false,'Compact floor fits half-size window');
assert.equal(await page.locator('.legend').isVisible(),false,'Interior has no legend or return toolbar');
assert.equal(await page.locator('#titlebar > span').isVisible(),false);
assert.equal(await page.locator('#collapse').isVisible(),false);
assert.equal(await page.locator('.floor-heading').isVisible(),false);
assert.equal(await page.locator('#pin').isVisible(),true);assert.equal(await page.locator('#close').isVisible(),true);
await page.evaluate(()=>window._bridgeActions=[]);const sceneBox=await page.locator('.scene').boundingBox();await page.mouse.move(sceneBox.x+20,sceneBox.y+20);await page.mouse.down();await page.mouse.move(sceneBox.x+35,sceneBox.y+30);await page.mouse.up();
assert.ok(await page.evaluate(()=>window._bridgeActions.includes('drag')),'Floor scene must request native dragging');
await page.screenshot({path:path.join(__dirname,'runtime/gothic-interior-smoke.png')});
assert.equal(await page.locator('.employee-marker').count(),2);
assert.equal(await page.locator('.employee-marker').first().getAttribute('data-character'),'mage');
const assignedModels=await page.locator('.employee-marker').evaluateAll(nodes=>nodes.map(n=>n.dataset.model));
await page.evaluate(data=>window.Tower.acceptSnapshot(data),sample);
assert.deepEqual(await page.locator('.employee-marker').evaluateAll(nodes=>nodes.map(n=>n.dataset.model)),assignedModels,'Employee models must remain stable across snapshots');
const animationA=await page.locator('.room canvas').screenshot();await page.waitForTimeout(420);const animationB=await page.locator('.room canvas').screenshot();await page.waitForTimeout(420);const animationC=await page.locator('.room canvas').screenshot();
assert.ok(!animationA.equals(animationB)||!animationA.equals(animationC),'Employee animations must visibly change the canvas');
const employeeTips=await page.locator('.employee-marker').evaluateAll(nodes=>nodes.map(n=>n.title));
assert.ok(employeeTips[1].includes('Маг'));assert.ok(!employeeTips[1].includes('Основной агент'),'Employee tooltip must not list other people');
assert.equal(await page.locator('.room').getAttribute('title'),null,'No combined room tooltip');
assert.equal(await page.locator('#details').isVisible(),false,'Interior must not restore the removed summary');
assert.equal(await page.locator('footer').isVisible(),false,'Interior must not show the service footer');
assert.equal(await page.locator('#task-title').getAttribute('title'),null,'Removed summary must not have a hover tooltip');
assert.equal(await page.locator('.tower-floor[data-project="second"]').count(),0);
assert.equal(await page.locator('.room .caption').count(),0,'No name/status strip beneath the room');
assert.equal(await page.locator('body').evaluate(el=>getComputedStyle(el).backgroundColor),'rgba(0, 0, 0, 0)','Interior background must be transparent');
assert.equal(await page.locator('.scene').evaluate(el=>getComputedStyle(el).backgroundColor),'rgba(0, 0, 0, 0)');
const before=await page.locator('#room-grid').boundingBox();await page.locator('.room[data-session="a"]').click();assert.deepEqual(await page.locator('#room-grid').boundingBox(),before);
await page.locator('#room-grid').evaluate(n=>n.scrollTop=100);const saved=await page.locator('#room-grid').evaluate(n=>n.scrollTop);await page.evaluate(data=>window.Tower.acceptSnapshot(data),sample);assert.equal(await page.locator('#room-grid').evaluate(n=>n.scrollTop),saved);
for(const width of [470,650,1000]){await page.setViewportSize({width,height:560});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth||document.documentElement.scrollHeight>innerHeight),false)}
await page.locator('#back-icon').click();await page.setViewportSize({width:650,height:560});
assert.equal(await page.locator('#back-icon').isVisible(),false);
const many=structuredClone(sample);many.projects[0].rooms=Array.from({length:16},(_,i)=>({...sample.projects[0].rooms[1],id:'session-'+String(i).padStart(2,'0'),title:'Сессия '+i}));
await page.evaluate(data=>window.Tower.acceptSnapshot(data),many);
const towerBox=await page.locator('.project-tower[data-project="p"]').boundingBox();
for(const node of await page.locator('.project-tower[data-project="p"] .overview-floor').all()){const box=await node.boundingBox();assert.ok(box.y>=towerBox.y && box.y+box.height<=towerBox.y+towerBox.height,'All session floors fit inside their project tower')}
assert.equal(await page.locator('.project-tower[data-project="p"]').getAttribute('data-distance'),'far');
const scales=await page.locator('.project-tower[data-project="p"] .overview-tower').evaluate(el=>{const m=new DOMMatrix(getComputedStyle(el).transform);return {x:m.a,y:m.d}});
assert.ok(Math.abs(scales.x-scales.y)<.001,'Tower must scale uniformly, without flattened floors');
assert.ok(scales.x<.5,'Long tower must recede into the distance');
await page.screenshot({path:path.join(__dirname,'runtime/tower-perspective-smoke.png')});
await page.evaluate(data=>window.Tower.acceptSnapshot(data),sample);
await page.screenshot({path:path.join(__dirname,'runtime/html-overlay-smoke.png')});
const litPixels=await warmPixels(page.locator('.overview-floor[data-session="a"]'));
await page.evaluate(data=>{data.updatedAt=1;window.Tower.acceptSnapshot(data)},sample);assert.equal(await page.locator('.overview-floor.is-active').count(),0);
const darkPixels=await warmPixels(page.locator('.overview-floor[data-session="a"]'));assert.ok(litPixels>darkPixels+5,'Working windows must visibly light up, not just change CSS classes');
assert.deepEqual(errors,[]);
}finally{await browser.close()}
});
