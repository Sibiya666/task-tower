import {readFileSync,writeFileSync} from 'node:fs';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {dirname,join} from 'node:path';
import {renderFrames,spriteSheet,save} from 'file:///C:/Users/sibiya666/.codex/lib/pixelfx/tools/lib/fxlib.mjs';
const root=dirname(fileURLToPath(import.meta.url)),source=join(root,'vendor/pixelfx/src/fx/weather');
// Keep licensed upstream recipes local; remove the moon and the opaque rain haze/floor.
const cloudFile=join(source,'clouds.js');let clouds=readFileSync(cloudFile,'utf8');
clouds=clouds.replace('  moon(q, C);','  // Moon omitted for a day/night-neutral overlay.');
clouds=clouds.replace(/  q\.glow\(MX, MY, (110|40|18),[^\n]+\n/g,'');writeFileSync(cloudFile,clouds);
const rainFile=join(source,'rain.js');let rain=readFileSync(rainFile,'utf8').replace(/\r\n/g,'\n');
rain=rain.replace(/export function drawBack\(p, t, o\) \{[\s\S]*?\n\}\n\nexport function draw\(/,`export function drawBack(p, t, o) {
  const q = clip(p, meta), S = o.seed, C = fit(o.palette, 8), P = pools(S);
  for (let L = 0; L < 3; L++) layer(q, t, S, C, P, L, o.density);
}

export function draw(`);writeFileSync(rainFile,rain);
for(const name of ['clouds','rain','fog']){
 const mod=await import(pathToFileURL(join(source,name+'.js')).href),fx={mod,meta:mod.meta,id:'weather/'+name};
 const frames=renderFrames(fx,{fps:6,bg:'none',actor:false}),sheet=spriteSheet(fx,frames,name);
 save(join(root,'web/assets/world-'+name+'.png'),sheet.png);
 writeFileSync(join(root,'web/assets/world-'+name+'.json'),JSON.stringify(sheet.json));
 console.log(name+': '+frames.n+' frames; transparent overlay without backdrop');
}
