const sharp=require('C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const fs=require('node:fs');const path=require('node:path');
(async()=>{
 const result={};
 for(const [tier,targetWidth,targetHeight] of [['cabinet',240,160],['workshop',340,227],['hall',460,307],['wings',580,387]])for(let v=0;v<3;v++){
  const id=tier+'-'+v,name='room-'+id;
  const source=path.join(__dirname,'assets/room-skins',id+'.png');
  const resized=await sharp(source).trim({threshold:8}).resize(targetWidth,targetHeight,{fit:'contain',background:{r:0,g:0,b:0,alpha:0},kernel:'nearest'}).ensureAlpha().png().toBuffer();
  const image=await sharp(resized).trim({threshold:8}).png().toBuffer();
  const {width,height}=await sharp(image).metadata();
  await sharp(image).toFile(path.join(__dirname,'web/assets',name+'.png'));
  const {data,info}=await sharp(image).raw().toBuffer({resolveWithObject:true});
  const mask=Buffer.alloc(data.length),groups=[];
  for(let y=0;y<height;y++)for(let x=0;x<width;x++){
   const p=(y*width+x)*4,[r,g,b,a]=data.subarray(p,p+4);
   if(y<height*.63&&b>75&&b>r*1.5&&b>g*1.12&&r<115){mask[p]=mask[p+1]=mask[p+2]=255;mask[p+3]=a;}
   if(y<height*.63&&r>205&&g>125&&g<230&&b<115&&a>180){
    let group=groups.find(q=>Math.hypot(q.x/q.n-x,q.y/q.n-y)<12);
    if(!group){group={x:0,y:0,n:0};groups.push(group)}group.x+=x;group.y+=y;group.n++;
   }
  }
  await sharp(mask,{raw:info}).png().toFile(path.join(__dirname,'web/assets',name+'-glass.png'));
  const lights=groups.filter(q=>q.n>=3).sort((a,b)=>b.n-a.n).slice(0,5).map(q=>[Math.round(q.x/q.n),Math.round(q.y/q.n)]);
  result[id]={width,height,lights};
 }
 fs.writeFileSync(path.join(__dirname,'web/room-skins.js'),'window.RoomSkins='+JSON.stringify(result)+';\n');
 console.log('Prepared 12 complete scenes with glass masks and light anchors');
})().catch(e=>{console.error(e);process.exit(1)});
