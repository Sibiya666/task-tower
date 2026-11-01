const {test}=require('node:test');const assert=require('node:assert/strict');const path=require('node:path');
const {chromium}=require('C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
test('Narrow overview wraps plots without clipping; expanded tower stays in its plot',async()=>{
 const b=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const p=await b.newPage({viewport:{width:650,height:560}});await p.goto('file:///'+path.join(__dirname,'web/index.html').replaceAll('\\','/'));await p.waitForFunction(()=>window.Tower?.ready);
  await p.evaluate(()=>window.Tower.acceptSnapshot({updatedAt:Date.now()/1000,projects:Array.from({length:3},(_,i)=>({id:'p'+i,name:'P'+i,rooms:Array.from({length:i===1?16:1},(_,j)=>({id:'r'+i+'-'+j,title:'Session '+j,status:'active',label:'Working',agents:[]}))}))}));
  for(const width of [650,470,1000]){
   await p.setViewportSize({width,height:560});await p.waitForFunction(()=>{const root=document.getElementById('overview');return root.scrollWidth<=root.clientWidth&&[...document.querySelectorAll('.tower-art-canvas')].every(e=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1})});
   for(const canvas of await p.locator('.tower-art-canvas').all()){const box=await canvas.boundingBox();assert.ok(box.x>=0&&box.x+box.width<=width+1,'Complete tower must fit horizontally at '+width)}
   assert.equal(await p.locator('#overview').evaluate(e=>e.scrollWidth>e.clientWidth),false,'No hidden horizontal field at '+width);
  }
  await p.locator('.tower-capacity').click();await p.locator('#world-menu button').filter({hasText:'Показать все этажи на башне'}).click();
  const plot=await p.locator('.project-tower[data-project="p1"]').boundingBox(),art=await p.locator('.project-tower[data-project="p1"] .tower-art-canvas').boundingBox();assert.ok(art.y>=plot.y,'Expanded roof must not escape its plot');
  await p.mouse.click(440,500,{button:'right'});await p.setViewportSize({width:340,height:300});await p.waitForTimeout(100);
  const menu=await p.locator('#world-menu').boundingBox();assert.ok(menu.x>=0&&menu.y>=0&&menu.x+menu.width<=340&&menu.y+menu.height<=300,'Settings must re-clamp when the viewport shrinks');
 }finally{await b.close()}
});
