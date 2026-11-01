(function(root){'use strict';
const defaults={mode:'auto',weather:'clear',effects:true,idleMinutes:30,showHidden:false};
function normalizeSettings(input={}){return {
 mode:['auto','day','night'].includes(input.mode)?input.mode:defaults.mode,
 weather:['clear','clouds','rain','fog'].includes(input.weather)?input.weather:defaults.weather,
 effects:input.effects!==false,idleMinutes:[0,10,30,60].includes(input.idleMinutes)?input.idleMinutes:30,showHidden:input.showHidden===true
}}
function daylight(hour,mode='auto'){
 if(mode==='day')return 1;if(mode==='night')return 0;
 const rise=Math.max(0,Math.min(1,(hour-6)/2)),set=Math.max(0,Math.min(1,(20-hour)/2));
 const t=Math.min(rise,set);return t*t*(3-2*t);
}
function phase(hour,mode='auto'){if(mode!=='auto')return mode;if(hour<6||hour>=20)return 'night';if(hour<8)return 'dawn';if(hour>=18)return 'dusk';return 'day'}
function towerDetail(total,expanded=false){total=Math.max(1,total);return {total,levels:total>8&&!expanded?4:total,far:total>8}}
function floorBand(index,total,levels){
 for(let level=0;level<levels;level++){
  const start=Math.floor(level*total/levels),end=Math.floor((level+1)*total/levels);
  if(index>=start&&index<end)return {level,top:level+(index-start)/(end-start),height:1/(end-start)};
 }
 return {level:0,top:0,height:1};
}
class WorldVisibility{
 constructor(saved={}){this.records=new Map(Object.entries(saved).filter(([,v])=>v&&Number.isFinite(v.since)&&typeof v.hidden==='boolean'))}
 hidden(project,now,fresh,delay){
  const old=this.records.get(project.id);if(!fresh)return old?.hidden||false;
  const agents=project.rooms.flatMap(r=>[r,...(r.agents||[])]),protectedState=agents.some(a=>['active','waiting','unknown','stale','error'].includes(a.status));
  if(protectedState||delay===0){this.records.set(project.id,{since:now,hidden:false});return false}
  const last=Math.max(0,...agents.map(a=>Number(a.lastEvent)||0));
  const since=old?Math.min(now,Math.max(old.since,last)):Math.min(now,last||now),hidden=now-since>=delay;
  this.records.set(project.id,{since,hidden});return hidden;
 }
 serialize(){return Object.fromEntries(this.records)}
}
const api={daylight,phase,towerDetail,floorBand,WorldVisibility,normalizeSettings};
if(typeof module!=='undefined')module.exports=api;else root.WorldPolicy=api;
})(globalThis);
