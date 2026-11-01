const sharp=require('C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{
 const dir=path.join(__dirname,'../docs/screenshots'),parts=[];
 for(const [i,id] of ['overview','study','hall'].entries()){
  const content=await sharp(path.join(dir,'processed',id+'.png')).trim({threshold:12}).resize(896,576,{fit:'inside',kernel:'nearest'}).png().toBuffer();
  const {width,height}=await sharp(content).metadata();
  const file=path.join(dir,id+'.png');
  await sharp({create:{width:960,height:640,channels:4,background:{r:0,g:0,b:0,alpha:0}}}).composite([{input:content,left:Math.floor((960-width)/2),top:Math.floor((640-height)/2)}]).png().toFile(file);
  const meta=await sharp(file).metadata(),stats=await sharp(file).stats();
  assert.equal(meta.width,960);assert.equal(meta.height,640);assert.ok(meta.hasAlpha);assert.equal(stats.channels[3].min,0);
  parts.push({input:await sharp(file).resize(480,320,{kernel:'nearest'}).png().toBuffer(),left:i*480,top:0});
  console.log(id+': 960x640 PNG, transparent alpha, proportional fit');
 }
 await sharp({create:{width:1440,height:320,channels:4,background:'#11191e'}}).composite(parts).png().toFile(path.join(dir,'gallery.png'));
})().catch(e=>{console.error(e);process.exit(1)});
