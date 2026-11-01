const sharp=require('C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const fs=require('node:fs');const path=require('node:path');
(async()=>{
const source=path.join(__dirname,'assets/tower-unified-source.png');
// All slices share the SAME X interval; no separate crop, camera or centering.
const slices={roof:{top:0,height:548},floor:{top:548,height:405},base:{top:953,height:583}};
const heights={};for(const [part,rect] of Object.entries(slices)){
 const dest=path.join(__dirname,'web/assets/tower-aligned-'+part+'.png');
 await sharp(source).extract({left:128,top:rect.top,width:768,height:rect.height}).resize({width:512,kernel:'nearest'}).png().toFile(dest);
 heights[part]=(await sharp(dest).metadata()).height*134/512;
}
const {data,info}=await sharp(path.join(__dirname,'web/assets/tower-aligned-floor.png')).ensureAlpha().raw().toBuffer({resolveWithObject:true});
const mask=Buffer.alloc(info.width*info.height*4);
for(let y=0;y<info.height;y++)for(let x=0;x<info.width;x++){
 const i=(y*info.width+x)*4;
 // Restrict dark-glass detection to the two shared-axis arched window recesses.
 const inWindow=y>=94&&y<=224&&((x>=145&&x<=180)||(x>=330&&x<=368));
 if(inWindow&&data[i]<22&&data[i+1]<32&&data[i+2]<40&&data[i+3]>220){mask[i]=255;mask[i+1]=255;mask[i+2]=255;mask[i+3]=220;}
}
const png=await sharp(mask,{raw:{width:info.width,height:info.height,channels:4}}).png().toBuffer();
fs.writeFileSync(path.join(__dirname,'web/assets/tower-aligned-window-mask.png'),png);
const css=`/* Generated from one coherent sprite; do not independently reposition slices. */
:root{--tower-roof-h:${heights.roof}px;--tower-floor-h:${heights.floor}px;--tower-base-h:${heights.base}px}
.overview-tower{height:calc(var(--tower-roof-h) + var(--floors)*var(--tower-floor-h) + var(--tower-base-h));grid-template-rows:var(--tower-roof-h) repeat(var(--floors),var(--tower-floor-h)) var(--tower-base-h)}
.overview-tower .overview-roof{background-image:url('assets/tower-aligned-roof.png');background-size:134px auto;margin:0}
.project-tower .overview-floor,.project-tower .dense .overview-floor{height:var(--tower-floor-h);background-image:url('assets/tower-aligned-floor.png');background-size:134px auto}
.overview-tower .overview-foundation{background-image:url('assets/tower-aligned-base.png');background-size:134px auto;filter:none;margin:0}
.project-tower .overview-floor:after{mask-image:url('data:image/png;base64,${png.toString('base64')}');mask-size:134px auto}
`;
fs.writeFileSync(path.join(__dirname,'web/tower-art.css'),css);
fs.writeFileSync(path.join(__dirname,'assets/tower-alignment.json'),JSON.stringify({source:'tower-unified-source.png',sharedX:128,sharedWidth:768,slices,renderHeights:heights},null,2));
console.log(heights);
})().catch(e=>{console.error(e);process.exit(1)});
