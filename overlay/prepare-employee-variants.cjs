const sharp=require('C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const path=require('node:path');
(async()=>{
 const source=path.join(__dirname,'assets/employee-variants-source.png');
 const m=await sharp(source).metadata();
 for(const [row,group] of ['smith','ranger','scholar'].entries())for(let col=0;col<3;col++){
  const left=Math.floor(col*m.width/3),top=Math.floor(row*m.height/3);
  const cell=await sharp(source).extract({left,top,width:Math.floor((col+1)*m.width/3)-left,height:Math.floor((row+1)*m.height/3)-top}).png().toBuffer();
  await sharp(cell).trim({threshold:10}).resize({width:84,height:88,fit:'contain',position:'bottom',background:{r:0,g:0,b:0,alpha:0},kernel:'nearest'}).png().toFile(path.join(__dirname,`web/assets/employee-${group}-${col+1}.png`));
 }
 console.log('Prepared 9 transparent employee variants (84x88)');
})().catch(e=>{console.error(e);process.exit(1)});
