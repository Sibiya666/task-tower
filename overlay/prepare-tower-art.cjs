const sharp=require('C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const path=require('node:path');
(async()=>{
for(const part of ['roof','floor','base']){
 const source=path.join(__dirname,'assets','tower-'+part+'-source.png');
 const {data,info}=await sharp(source).ensureAlpha().raw().toBuffer({resolveWithObject:true});
 let left=info.width,top=info.height,right=0,bottom=0;
 for(let y=0;y<info.height;y++)for(let x=0;x<info.width;x++){if(data[(y*info.width+x)*4+3]>100){left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y)}}
 const crop={left,top,width:right-left+1,height:bottom-top+1};
 await sharp(source).extract(crop).resize({width:512,kernel:'nearest'}).png().toFile(path.join(__dirname,'web/assets','tower-'+part+'.png'));
 console.log(part,crop);
}
})().catch(e=>{console.error(e);process.exit(1)});
