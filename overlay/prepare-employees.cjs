const sharp=require('C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const path=require('node:path');
(async()=>{
const source=path.join(__dirname,'assets/employee-sprites-source.png'),metadata=await sharp(source).metadata();
const names=['scholar','smith','ranger','mage'];
for(let i=0;i<4;i++){
const left=Math.floor(i*metadata.width/4),right=Math.floor((i+1)*metadata.width/4);
const cut=await sharp(source).extract({left,top:0,width:right-left,height:metadata.height}).png().toBuffer();
await sharp(cut).trim({threshold:10}).resize({width:84,height:88,fit:'contain',position:'bottom',background:{r:0,g:0,b:0,alpha:0},kernel:'nearest'}).png().toFile(path.join(__dirname,'web/assets/employee-'+names[i]+'.png'));
}
console.log('Prepared 4 transparent employee sprites, 84x88, shared baseline');
})().catch(e=>{console.error(e);process.exit(1)});
