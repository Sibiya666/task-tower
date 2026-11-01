const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
const browser=await chromium.launch({headless:true,channel:'msedge'});
const page=await browser.newPage({viewport:{width:800,height:600}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
let html=fs.readFileSync('C:/Users/sibiya666/.codex/visualizations/2026/10/31/01a19222-b86c-7741-941b-047cf523feaf/agent-tower.html','utf8');
// Export the approved procedural artwork without mock labels or mock agents.
html=html.replace("window.addEventListener('openai:set_globals'", "window.towerArt={ctx,canvas,details,hero,rect,colors};window.addEventListener('openai:set_globals'");
await page.setContent(html);
fs.mkdirSync(path.join(__dirname,'assets'),{recursive:true});
for(const type of ['book','forge','map']){
 const data=await page.evaluate(type=>{
 const a=window.towerArt;a.canvas.width=193;a.canvas.height=224;a.rect(0,0,193,224,a.colors.wall);a.details(0,0,type);
 // Deep recesses and material highlights from the approved room design.
 a.rect(71,37,51,93,'#0c151d');a.rect(79,39,34,65,'#304b59');a.rect(84,41,24,57,'#8cafbc');a.rect(94,40,4,64,'#273943');a.rect(81,66,31,4,'#273943');
 for(const tx of [29,158]){a.rect(tx-4,85,12,8,'#2c211e');a.rect(tx,85,4,24,'#7c705b');a.rect(tx-2,76,8,14,'#9b5e36');a.rect(tx,73,4,13,'#e0a35e');a.rect(tx+1,77,2,8,'#e5c695')}
 a.rect(46,145,99,7,'#5d4a37');a.rect(49,151,7,25,'#372c27');a.rect(134,151,7,25,'#372c27');a.rect(51,152,2,23,'#77634b');a.rect(135,152,2,23,'#77634b');a.rect(46,140,99,4,'#a08a63');
 if(type==='book'){a.rect(59,130,31,11,'#d0c3a3');a.rect(74,130,2,11,'#796c53');for(let k=0;k<3;k++)a.rect(62,133+k*2,8,1,'#8e846c');a.rect(108,128,17,12,'#6f4844');a.rect(109,128,15,2,'#b4a285')}
 if(type==='forge'){a.rect(85,127,40,8,'#9ba9aa');a.rect(96,135,20,7,'#51626a');a.rect(95,141,23,3,'#85969c')}
 if(type==='map'){a.rect(60,129,65,11,'#c5b990');for(let k=0;k<7;k++)a.rect(66+k*7,132+k%3,5,1,'#657369')}
 return a.canvas.toDataURL('image/png').split(',')[1];
 },type);fs.writeFileSync(path.join(__dirname,'assets',type+'.png'),Buffer.from(data,'base64'));
}
for(const type of ['book','forge','map']){
 const data=await page.evaluate(type=>{const a=window.towerArt;a.canvas.width=42;a.canvas.height=44;a.ctx.clearRect(0,0,42,44);a.hero(2,7,type==='book'?'#596e87':type==='forge'?'#77797b':'#596b51',type);return a.canvas.toDataURL('image/png').split(',')[1]},type);
 fs.writeFileSync(path.join(__dirname,'assets','hero-'+type+'.png'),Buffer.from(data,'base64'));
}
if(errors.length)throw Error(errors.join('\n'));
await browser.close();console.log('Exported 3 rooms and 3 transparent hero sprites.');
})().catch(e=>{console.error(e);process.exit(1)});
