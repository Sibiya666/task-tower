const {test}=require('node:test');const assert=require('node:assert/strict');
const {daylight,towerDetail,floorBand,WorldVisibility,normalizeSettings}=require('./web/world-policy.js');
test('Local day/night is continuous and manual modes override it',()=>{
 assert.equal(daylight(12,'auto'),1);assert.equal(daylight(0,'auto'),0);
 assert.ok(daylight(6.5,'auto')>0&&daylight(6.5,'auto')<1);
 assert.equal(daylight(0,'day'),1);assert.equal(daylight(12,'night'),0);
 assert.equal(normalizeSettings({weather:'injected',idleMinutes:-1}).weather,'clear');
});
test('Idle hiding persists, waiting/uncertain data is protected and activity revives',()=>{
 const project={id:'p',rooms:[{status:'completed',lastEvent:100,agents:[]}]};
 const p=new WorldVisibility();assert.equal(p.hidden(project,1000,true,1800),false);
 assert.equal(p.hidden(project,1901,true,1800),true);
 const restored=new WorldVisibility(p.serialize());assert.equal(restored.hidden(project,2000,true,1800),true);
 project.rooms[0].status='waiting';assert.equal(restored.hidden(project,2100,true,1800),false);
 project.rooms[0].status='unknown';assert.equal(restored.hidden(project,9999,true,1800),false);
 project.rooms[0].status='completed';assert.equal(restored.hidden(project,10000,false,1800),false);
 project.rooms[0].status='active';assert.equal(p.hidden(project,3000,true,1800),false);
});
test('Activity completed while closed advances persisted idle baseline',()=>{
 const p=new WorldVisibility({p:{since:100,hidden:true}}),project={id:'p',rooms:[{status:'completed',lastEvent:5000,agents:[]}]};
 assert.equal(p.hidden(project,5010,true,1800),false);assert.equal(p.hidden(project,6801,true,1800),true);
});
test('Uneven compact groups share exact painting/hitbox boundaries',()=>{
 for(const total of [9,10,11,16,17]){
  let end=0;
  for(let index=0;index<total;index++){
   const band=floorBand(index,total,4);assert.ok(Math.abs(band.top-end)<1e-9);
   assert.ok(index>=Math.floor(band.level*total/4)&&index<Math.floor((band.level+1)*total/4));end=band.top+band.height;
  }
  assert.ok(Math.abs(end-4)<1e-9);
 }
 assert.equal(floorBand(2,9,4).top,1);
});
test('Distant representation retains actual floor count without stretched modules',()=>{
 const near=towerDetail(2),far=towerDetail(16);assert.equal(near.levels,2);
 assert.equal(far.total,16);assert.ok(far.levels<16);assert.equal(towerDetail(16,true).levels,16);
});
