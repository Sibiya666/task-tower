(()=>{'use strict';
const $=id=>document.getElementById(id);
const palette={active:'#88b4c8',waiting:'#d6b67d',completed:'#819887',idle:'#81959d',stopped:'#c59082',error:'#e37d68',unknown:'#9aa7a9',stale:'#c39e67'};
const glyphs={active:['001111100','001111110','001111100','000110000','001100000','011000000','110000000','100000000','000000000'],idle:['111111111','010000010','001000100','000101000','000010000','000101000','001010100','011111110','111111111'],stopped:['000000000','011111110','011111110','011111110','011111110','011111110','011111110','011111110','000000000'],error:['000111000','000111000','000111000','000111000','000111000','000000000','000111000','000111000','000000000'],unknown:['001111100','011000110','000000110','000001100','000111000','000110000','000000000','000110000','000110000'],stale:['001111100','010000010','100010001','100010001','100011101','100000001','010000010','001111100','000000000']};
let data={projects:[]},projectId=null,selectedId=null,scenes=[],lastFrame=0,sourceBad=true,collapsed=false;
const sessions=p=>(p?.rooms||[]).slice().sort((a,b)=>String(a.id).localeCompare(String(b.id)));
const images={};
let overviewScenes=[];
const towerAgentIds=new Map(),towerArrivals=new Map();
let highlightedFloor=null;
let towerSlots=new Map();
try{towerSlots=new Map(Object.entries(JSON.parse(localStorage.getItem('tower-slots')||'{}')).filter(([,v])=>Number.isInteger(v)&&v>=0))}catch{}
function slotFor(id){if(!towerSlots.has(id)){const used=new Set(towerSlots.values());let slot=0;while(used.has(slot))slot++;towerSlots.set(id,slot);try{localStorage.setItem('tower-slots',JSON.stringify(Object.fromEntries(towerSlots)))}catch{}}return towerSlots.get(id)}
let viewMode='overview',scrollToSession=null;
let sentViewMode=null;
let overviewPosition={left:0,top:0};
let enteredSkin=null;
glyphs.waiting=glyphs.idle;glyphs.idle=['000000000','000000000','000000000','000000000','001010100','000000000','000000000','000000000','000000000'];glyphs.completed=glyphs.stopped;
const presence=new window.AgentPresence();
const reducedMotion=()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function chooseSkin(room){
 const count=occupants(room).filter(a=>a.status!=='completed').length,panels=count<=4?1:count<=8?2:count<=16?3:4;
 const name=['cabinet','workshop','hall','wings'][panels-1],variant=roomSeed(room)%3,id=name+'-'+variant;
 return {roomId:room.id,name,id,variant,columns:[4,6,8,12][panels-1],...window.RoomSkins[id]};
}
function skinFor(room){return enteredSkin?.roomId===room.id?enteredSkin:chooseSkin(room)}
const bridge=action=>window.chrome?.webview?.postMessage({action});
const title=(node,text)=>{node.textContent=text;node.removeAttribute('title')};
function state(agent){return sourceBad?'unknown':palette[agent.status]?agent.status:'unknown'}
function occupants(room){return [room,...(room.agents||[]).slice().sort((a,b)=>String(a.id).localeCompare(String(b.id)))]}
function project(){return data.projects.find(p=>p.id===projectId)}
function selected(){return project()?.rooms.find(r=>r.id===selectedId)}
function freshness(){const bad=!!data.error||!data.updatedAt||Date.now()/1000-data.updatedAt>12;const changed=bad!==sourceBad;sourceBad=bad;$('source-dot').style.color=bad?palette.error:palette.active;$('source').textContent=bad?(data.error?'Ошибка источника: '+data.error:'Источник не обновляется · статусы неизвестны'):'Локальный Codex · только чтение · обновление каждые 3 с';if(changed)render()}
function details(room){if(!room){title($('task-title'),'На этом этаже пока нет задач');$('task-status').textContent='';$('agent-names').textContent='';return}title($('task-title'),room.title||'Без названия');const people=occupants(room),working=people.filter(a=>state(a)==='active').length;title($('task-status'),(sourceBad?'Статус неизвестен':room.label)+' · агентов: '+people.length+' · работают: '+working);$('task-status').style.color=palette[state(room)];title($('agent-names'),people.map((a,i)=>(i===0?'Основной агент':a.agent_nickname||'Субагент')+': '+(sourceBad?'Статус неизвестен':a.label)).join(' · '))}
function badge(ctx,status,x,y,frame){
 const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
 const step=reduced?0:Math.floor(frame)%16;
 ctx.save();ctx.translate(Math.round(x),Math.round(y));
 ctx.fillStyle='#101b22';ctx.fillRect(-2,-2,22,22);ctx.strokeStyle=palette[status];ctx.lineWidth=1;ctx.strokeRect(-2.5,-2.5,23,23);
 const pixel=(px,py,color=palette[status])=>{ctx.fillStyle=color;ctx.fillRect(px,py,2,2)};
 const glyph=()=>glyphs[status].forEach((line,row)=>[...line].forEach((p,col)=>{if(p==='1')pixel(col*2,row*2)}));
 if(status==='active'){
  // A held tool winds up, strikes and rests; the frame and hitbox stay still.
  const angles=[-.45,-.45,-.3,-.15,0,.25,.5,.5,.25,0,0,0,0,0,0,0];
  ctx.save();ctx.translate(5,14);ctx.rotate(reduced?0:angles[step]);ctx.translate(-5,-14);glyph();ctx.restore();
  if(!reduced&&step>=6&&step<=9){const d=step-6;pixel(14+d,13-d,'#ffe1a0');if(d<3)pixel(12-d,16+d,'#d9a65e')}
 }else if(status==='waiting'&&!reduced){
  // Keep the glass outline fixed while the two sand piles exchange pixels.
  ['111111111','010000010','001000100','000101000','000010000','000101000','001000100','010000010','111111111'].forEach((line,row)=>[...line].forEach((p,col)=>{if(p==='1')pixel(col*2,row*2)}));
  const fill=Math.floor(step/4);
  for(let row=0;row<3-fill;row++)for(let col=0;col<5-row*2;col++)pixel(4+row*2+col*2,2+row*2,'#f2d494');
  for(let row=0;row<=fill;row++)for(let col=0;col<Math.min(7,1+row*2);col++)pixel(8-Math.min(3,row)*2+col*2,14-(fill-row)*2,'#f2d494');
  pixel(8,8+(step%3)*2,'#fff0be');
 }else glyph();
 ctx.restore();
}
function roomSeed(room){let h=0;for(const c of String(room.id))h=(h*31+c.charCodeAt(0))>>>0;return h}
function employeeLayout(j,count,room){
 const skin=skinFor(room);
 const columns=Math.min(skin.columns,count),rows=Math.ceil(count/columns),cell=(skin.width-40)/columns;
 const available=skin.height*.30,step=available/rows,h=Math.min(40,step*.58),w=h*.95;
 const seed=roomSeed(room),row=Math.floor(j/columns),col=(j+seed%columns)%columns;
 return {x:20+col*cell+(cell-w)/2+((j*7+seed)%7)-3,y:skin.height*.61+row*step+step-h-4-(col%2)*Math.min(10,step*.18)+((j*3+seed)%7)-3,w,h};
}
function atmosphere(ctx,frame,reduced,skin){
 const t=reduced?0:frame*.14;
 const layer=images['ambient-layer'],sky=layer.getContext('2d');
 layer.width=skin.width;layer.height=skin.height;sky.imageSmoothingEnabled=false;
 const cloud=Math.floor(t*8)%96;
 sky.drawImage(images['ambient-clouds'],(cloud%8)*320,Math.floor(cloud/8)*180,320,180,0,0,skin.width,skin.height*.66);
 sky.globalCompositeOperation='destination-in';sky.drawImage(images['room-'+skin.id+'-glass'],0,0);sky.globalCompositeOperation='source-over';
 ctx.save();ctx.globalAlpha=.72;ctx.drawImage(layer,0,0);ctx.restore();
 // The scene silhouette clips warm spill so the desktop remains transparent.
 sky.clearRect(0,0,skin.width,skin.height);
 for(const [i,[x,y]] of skin.lights.entries()){
  const flicker=.8+.1*Math.sin(t*3.3+i*2)+.07*Math.sin(t*7.1+i);
  const radius=skin.width*.13,glow=sky.createRadialGradient(x,y,1,x,y,radius);
  glow.addColorStop(0,'rgba(255,185,79,'+(.2*flicker)+')');glow.addColorStop(1,'rgba(255,150,45,0)');
  sky.fillStyle=glow;sky.fillRect(x-radius,y-radius,radius*2,radius*2);
 }
 sky.globalCompositeOperation='destination-in';sky.drawImage(images['room-'+skin.id],0,0);sky.globalCompositeOperation='source-over';
 ctx.save();ctx.globalCompositeOperation='screen';ctx.drawImage(layer,0,0);ctx.restore();
 for(const [i,[x,y]] of skin.lights.entries()){
  const f=Math.floor(t*8+i*11)%32;
  ctx.drawImage(images['ambient-candle'],(f%7)*56,Math.floor(f/7)*76,56,76,x-5,y-7,10,14);
 }
}
function employeeCharacter(agent,index){
 if(index===0)return 'mage';const role=(agent.agent_role||'').toLowerCase();
 if(/review|test|audit|check|qa/.test(role))return 'ranger';
 if(/art|design|research|analys|lore/.test(role))return 'scholar';
 if(/develop|engineer|worker|implement|code|build|fix/.test(role))return 'smith';
 if(/coord|manager|plan/.test(role))return 'mage';
 const key=String(agent.id||agent.agent_nickname||index);let hash=0;for(const c of key)hash=(hash*31+c.charCodeAt(0))>>>0;
 return ['scholar','smith','ranger','mage'][hash%4];
}
function employeeModel(agent,index){
 const group=employeeCharacter(agent,index);
 if(group==='mage')return group;
 let hash=0;for(const c of String(agent.id||agent.agent_nickname||index))hash=(hash*31+c.charCodeAt(0))>>>0;
 const variant=hash%4;return group+(variant?'-'+variant:'');
}
function draw(frame){
const reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
for(const {canvas,room} of scenes){
 const skin=skinFor(room),ctx=canvas.getContext('2d');ctx.imageSmoothingEnabled=false;ctx.clearRect(0,0,canvas.width,canvas.height);
 ctx.drawImage(images['room-'+skin.id],0,0);atmosphere(ctx,frame,reduce,skin);
 const people=presence.frame(room.id,performance.now(),reduce);
 for(const marker of canvas.parentElement.querySelectorAll('.employee-marker')){
  const item=people.find(v=>String(v.agent.id)===marker.dataset.agentId);
  if(!item){marker.remove();continue}marker.dataset.motion=item.motion;marker.style.opacity=item.motion==='exiting'?String(1-item.progress):'1';marker.style.pointerEvents=item.motion==='present'?'':'none';
 }
 people.map((item,j)=>({...item,j,...employeeLayout(j,people.length,room)})).sort((a,b)=>a.y-b.y).forEach(({agent,index,j,motion,progress,x,y,w,h})=>{
  const s=state(agent),phase=(frame+j*7)*Math.PI/12;
  const walking=!reduce&&motion!=='present',active=!reduce&&s==='active',idle=!reduce&&(s==='idle'||s==='waiting');
  const breathe=active?Math.sin(phase)*.025:idle?Math.sin(phase*.5)*.018:0;
  const lift=active?Math.round(Math.sin(phase*2)*1.3):0;
  ctx.save();
  if(walking){const p=progress*progress*(3-2*progress),k=motion==='entering'?1-p:p;ctx.translate((skin.width*.5-x)*k,(skin.height*.91-y-h)*k);ctx.globalAlpha=motion==='entering'?progress:1-progress;ctx.translate(0,Math.sin(frame*2)*1.4)}
  ctx.filter='brightness(1.08) contrast(1.06)';ctx.shadowColor='#071015';ctx.shadowBlur=2;ctx.shadowOffsetY=1;
  ctx.translate(x+w/2,y+h-lift);ctx.rotate(active?Math.sin(phase)*.02:0);ctx.scale(1,1+breathe);
  ctx.drawImage(images['employee-'+employeeModel(agent,index)],-w/2,-h,w,h);ctx.restore();
  if(motion==='present'){const bs=Math.min(1,h/32);ctx.save();ctx.translate(x+w/2-9*bs,y-22*bs);ctx.scale(bs,bs);badge(ctx,s,0,0,frame);ctx.restore()}
 });
 canvas.parentElement._positionMarkers?.();
}
}
function makeRoom(room,i,p){
const button=document.createElement('button');button.type='button';button.className='room';button.setAttribute('aria-pressed',String(room.id===selectedId));button.setAttribute('data-agent-states',occupants(room).map(a=>state(a)).join(','));
button.dataset.session=room.id;
const skin=skinFor(room),scene=document.createElement('div');scene.className='scene';scene.dataset.skin=skin.name;scene.dataset.skinId=skin.id;const canvas=document.createElement('canvas');canvas.width=skin.width;canvas.height=skin.height;canvas.setAttribute('aria-label','Агенты и значки состояния');scene.append(canvas);
const roster=presence.sync(room.id,occupants(room),performance.now(),reducedMotion());
const markers=[];roster.forEach(({agent,index,motion},j)=>{
 const marker=document.createElement('span');marker.className='employee-marker';marker.tabIndex=0;marker.setAttribute('role','img');
 marker.dataset.character=employeeCharacter(agent,index);
 marker.dataset.model=employeeModel(agent,index);marker.dataset.agentId=String(agent.id);marker.dataset.status=state(agent);marker.dataset.motion=motion;
 const who=agent.agent_nickname||(index===0?'Основной агент':'Субагент');
 marker.title=who+'\nРоль: '+(agent.agent_role||(index===0?'Основной агент':'Субагент'))+'\nСтатус: '+(motion==='exiting'?'Выходит с этажа':sourceBad?'Статус неизвестен':agent.label);
 marker.setAttribute('aria-label',marker.title);marker.onclick=e=>e.stopPropagation();markers.push(marker);scene.append(marker);
});
const positionMarkers=()=>{const current=presence.frame(room.id,performance.now(),reducedMotion()),w=scene.clientWidth,h=scene.clientHeight,s=Math.min(w/skin.width,h/skin.height),ox=(w-skin.width*s)/2,oy=(h-skin.height*s)/2;markers.forEach(marker=>{const j=current.findIndex(item=>String(item.agent.id)===marker.dataset.agentId);if(j<0)return;const {x,y,w:sw,h:sh}=employeeLayout(j,current.length,room);marker.style.left=ox+(x-2)*s+'px';marker.style.top=oy+(y-25)*s+'px';marker.style.width=Math.max(26,sw+4)*s+'px';marker.style.height=(sh+26)*s+'px';marker.style.zIndex=String(Math.round(y))})};
scene._positionMarkers=positionMarkers;
const observer=new ResizeObserver(positionMarkers);observer.observe(scene);scene._markerObserver=observer;
button.append(scene);button.onclick=()=>{projectId=p.id;selectedId=room.id;render()};scenes.push({canvas,room,kind:['book','forge','map'][i]});return button;
}
function trackPosition(){
const view=$('room-grid'),floors=[...view.querySelectorAll('.tower-floor')];if(!floors.length)return;
const midpoint=view.scrollTop+view.clientHeight*.45;
const nearest=floors.reduce((best,f)=>Math.abs(f.offsetTop+f.offsetHeight/2-midpoint)<Math.abs(best.offsetTop+best.offsetHeight/2-midpoint)?f:best,floors[0]);
$('tower-map').querySelectorAll('.map-floor').forEach(b=>b.setAttribute('aria-current',String(b.dataset.session===nearest.dataset.session)));
const atTop=view.scrollTop<8,atBase=view.scrollTop+view.clientHeight>=view.scrollHeight-8;
const label=$('tower-map').querySelector('.map-position');if(label)label.textContent=atTop?'Верх\nбашни':atBase?'У\nоснования':'Этаж\n'+nearest.dataset.number;
}
function renderOverview(){
const returning=sentViewMode==='rooms'&&viewMode==='overview';
if(sentViewMode==='overview'&&viewMode==='rooms')overviewPosition={left:$('overview').scrollLeft,top:$('overview').scrollTop};
document.body.classList.toggle('overview-mode',viewMode==='overview');
if(sentViewMode!==viewMode){sentViewMode=viewMode;bridge(viewMode==='overview'?'overview-view':'floor-view')}
overviewScenes=[];
const root=$('overview');let district=root.querySelector('#overview-towers');if(!district){district=document.createElement('div');district.id='overview-towers';root.append(district)}
const oldFieldWidth=district.offsetWidth,oldFieldScroll=root.scrollLeft;
const columns=Math.max(1,...data.projects.map(p=>slotFor(p.id)%3+1));
district.style.gridTemplateColumns='repeat('+columns+',220px)';district.style.width='max(100%,'+(columns*220+(columns-1)*25+30)+'px)';district.style.justifyContent='end';
const allRooms=data.projects.flatMap(p=>p.rooms),lit=allRooms.filter(r=>occupants(r).some(a=>state(a)==='active')).length,total=allRooms.reduce((n,r)=>n+occupants(r).filter(a=>state(a)==='active').length,0);
const liveProjects=new Set(data.projects.map(p=>p.id));for(const node of [...district.children])if(!liveProjects.has(node.dataset.project))node.remove();
for(const p of data.projects){
const ordered=sessions(p),signature=ordered.map(r=>r.id).join('|'),previous=[...district.children].find(n=>n.dataset.project===p.id);
if(previous&&previous.dataset.signature===signature){previous.style.gridColumn=String(columns-slotFor(p.id)%3);previous.querySelector('.project-tower-name').textContent=p.name;overviewScenes.push({canvas:previous.querySelector('.tower-art-canvas'),ordered});continue}
const wrapper=document.createElement('section');wrapper.className='project-tower';wrapper.dataset.project=p.id;wrapper.dataset.signature=signature;wrapper.setAttribute('aria-label','Башня проекта '+p.name);
const arrivals=document.createElement('canvas');arrivals.className='tower-arrivals';arrivals.width=220;arrivals.height=90;arrivals.setAttribute('aria-hidden','true');wrapper.append(arrivals);
const slot=slotFor(p.id);wrapper.style.gridColumn=String(columns-slot%3);wrapper.style.gridRow=String(Math.floor(slot/3)+1);
wrapper.style.setProperty('--tower-ratio',Math.max(1,ordered.length)/Math.max(1,...data.projects.map(p=>p.rooms.length)));
wrapper.style.setProperty('--floor-count',Math.max(1,ordered.length));
const heading=document.createElement('button');heading.className='project-tower-name';heading.textContent=p.name;heading.title=p.name+' · сессий: '+ordered.length;heading.onclick=()=>{viewMode='rooms';projectId=p.id;selectedId=ordered.at(-1)?.id;scrollToSession=selectedId;render()};
const tower=document.createElement('div');tower.className='overview-tower'+(ordered.length>5?' dense':'');tower.style.setProperty('--floors',Math.max(1,ordered.length));const roof=document.createElement('div');roof.className='overview-roof';roof.title='Вершина · '+p.name;tower.append(roof);
const art=document.createElement('canvas');art.className='tower-art-canvas';art.setAttribute('aria-label','Башня '+p.name+' с подсветкой работающих сессий');tower.append(art);overviewScenes.push({canvas:art,ordered});
ordered.map((room,i)=>({room,number:i+1})).reverse().forEach(({room,number})=>{
const active=occupants(room).filter(a=>state(a)==='active').length;
const floor=document.createElement('button');floor.type='button';floor.className='overview-floor'+(active?' is-active':'')+(sourceBad?' source-unknown':'');floor.dataset.project=p.id;floor.dataset.session=room.id;floor.dataset.activeCount=active;
const highlight=()=>{highlightedFloor=room.id;drawOverview()};
const unhighlight=()=>{if(highlightedFloor===room.id){highlightedFloor=null;drawOverview()}};
floor.onpointerenter=highlight;floor.onpointerleave=unhighlight;floor.onfocus=highlight;floor.onblur=unhighlight;
floor.dataset.floorNumber=number;
floor.setAttribute('aria-label',p.name+' · этаж '+number+' · '+room.title+' · '+(sourceBad?'Статус неизвестен':active?'Работают: '+active:'Сейчас не работают'));floor.title=floor.getAttribute('aria-label');
const label=document.createElement('span');label.className='overview-floor-name';label.textContent=number+' · '+room.title;const count=document.createElement('span');count.className='overview-floor-count';count.textContent=sourceBad?'Нет данных':active?'Работают: '+active:'Тихий этаж';label.append(count);
const windows=document.createElement('span');windows.className='overview-windows';windows.setAttribute('aria-hidden','true');for(let i=0;i<3;i++){const w=document.createElement('span');w.className='overview-window';windows.append(w)}floor.append(label,windows);
floor.onclick=()=>{viewMode='rooms';projectId=p.id;selectedId=room.id;scrollToSession=room.id;render()};tower.append(floor);
});
if(!ordered.length){const empty=document.createElement('div');empty.className='empty';empty.textContent='Нет сессий';tower.append(empty)}
const base=document.createElement('div');base.className='overview-foundation';base.title='Основание · '+p.name;const door=document.createElement('div');door.className='base-door';base.append(door);tower.append(base);wrapper.append(heading,tower);if(previous)previous.replaceWith(wrapper);else district.append(wrapper);
}
for(const p of data.projects){const wrapper=[...district.children].find(n=>n.dataset.project===p.id),byId=new Map(p.rooms.map(r=>[r.id,r]));for(const button of wrapper.querySelectorAll('.overview-floor')){const room=byId.get(button.dataset.session),active=occupants(room).filter(a=>state(a)==='active').length;button.classList.toggle('is-active',active>0);button.classList.toggle('source-unknown',sourceBad);button.dataset.activeCount=active;button.title=p.name+' · '+room.title+' · '+(sourceBad?'Нет данных':active?'Работают: '+active:room.label);button.setAttribute('aria-label',button.title);const count=button.querySelector('.overview-floor-count');if(count)count.textContent=sourceBad?'Нет данных':active?'Работают: '+active:'Тихий этаж'}}
drawOverview();layoutTowerArt();
if(viewMode==='overview'&&!returning)root.scrollLeft=Math.max(0,oldFieldScroll+district.offsetWidth-oldFieldWidth);
if(returning){const restore=()=>{if(viewMode==='overview'){$('overview').scrollLeft=overviewPosition.left;$('overview').scrollTop=overviewPosition.top}};restore();requestAnimationFrame(restore)}
if(viewMode==='overview'){title($('task-title'),'Башни проектов');title($('task-status'),sourceBad?'Источник недоступен · свет не показывает активность':data.projects.length+' башен · '+lit+' этажей со светом · агентов работают: '+total);$('task-status').style.color=palette[sourceBad?'unknown':'active'];title($('agent-names'),'Башня — проект. Этаж — сессия. Свет в окнах — идёт работа. Нажми на этаж, чтобы войти.')}
}
function drawOverview(){
const style=getComputedStyle(document.documentElement),roof=parseFloat(style.getPropertyValue('--tower-roof-h')),floor=parseFloat(style.getPropertyValue('--tower-floor-h')),base=parseFloat(style.getPropertyValue('--tower-base-h'));
for(const {canvas,ordered} of overviewScenes){
const n=Math.max(1,ordered.length),h=roof+n*floor+base,dpr=Math.min(2,window.devicePixelRatio||1);
const drawingKey=ordered.map(r=>r.id+':'+occupants(r).some(a=>state(a)==='active')+':'+(r.id===highlightedFloor)).join('|')+':'+dpr;
if(canvas.dataset.drawingKey===drawingKey)continue;canvas.dataset.drawingKey=drawingKey;
canvas.width=Math.ceil(134*dpr);canvas.height=Math.ceil(h*dpr);canvas.style.height=h+'px';
const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);ctx.imageSmoothingEnabled=false;
ctx.drawImage(images['tower-aligned-roof'],0,0,134,roof);
for(let i=0;i<n;i++){
 const y=roof+i*floor,room=ordered[ordered.length-1-i];
 ctx.save();ctx.filter=room&&room.id===highlightedFloor?'brightness(1.16)':'none';ctx.drawImage(images['tower-aligned-floor'],0,y,134,floor);ctx.restore();
 if(room&&occupants(room).some(a=>state(a)==='active')){ctx.save();ctx.shadowColor='#eeb96e';ctx.shadowBlur=7;ctx.drawImage(images['lit-windows'],0,y,134,floor);ctx.restore();}
}
ctx.drawImage(images['tower-aligned-base'],0,roof+n*floor,134,base);
}
}
function layoutTowerArt(){
if(viewMode!=='overview')return;
document.querySelectorAll('.project-tower').forEach(wrapper=>{
const n=Math.max(1,wrapper.querySelectorAll('.overview-floor').length);
const artStyle=getComputedStyle(document.documentElement);
const naturalHeight=parseFloat(artStyle.getPropertyValue('--tower-roof-h'))+n*parseFloat(artStyle.getPropertyValue('--tower-floor-h'))+parseFloat(artStyle.getPropertyValue('--tower-base-h'));
const available=Math.max(80,wrapper.clientHeight-32);
let scale=Math.min(1,(wrapper.clientWidth-42)/134,available/naturalHeight);
const distance=Math.round((1-scale)*22);
scale=Math.min(scale,(available-distance)/naturalHeight);
wrapper.style.setProperty('--tower-scale',scale);
wrapper.style.setProperty('--inverse-scale',1/scale);
wrapper.style.setProperty('--distance',distance+'px');
wrapper.style.setProperty('--ground-scale',Math.max(.42,scale));
wrapper.dataset.distance=scale<.6?'far':'near';
});
}
function render(){
if(viewMode==='overview'){enteredSkin=null;presence.rooms.clear()}else if(selected()&&enteredSkin?.roomId!==selectedId)enteredSkin=chooseSkin(selected());
if(!window.Tower.ready)return;const view=$('room-grid'),scroll=view.scrollTop;for(const scene of view.querySelectorAll('.scene'))scene._markerObserver?.disconnect();scenes=[];view.replaceChildren();$('tower-map').replaceChildren();
if(!selected()){const p=data.projects.at(-1);projectId=p?.id;selectedId=p?.rooms[0]?.id}
const p=project();
sessions(p).map((room,i)=>({room,number:i+1})).filter(({room})=>room.id===selectedId).forEach(({room,number})=>{
const floor=document.createElement('section');floor.className='tower-floor session-floor';floor.dataset.project=p.id;floor.dataset.session=room.id;floor.dataset.number=number;floor.setAttribute('aria-label',p.name+' · этаж '+number+' · '+room.title);
const heading=document.createElement('header');heading.className='floor-heading';const no=document.createElement('span');no.className='floor-number';no.textContent=number+' ЭТАЖ';const name=document.createElement('span');name.className='floor-name';title(name,room.title);heading.append(no,name);
const rooms=document.createElement('div');rooms.className='floor-rooms';rooms.append(makeRoom(room,number%3,p));floor.append(heading,rooms);view.append(floor);
});
view.scrollTop=scroll;details(selected());draw(lastFrame);renderOverview();
if(scrollToSession){const floor=[...view.querySelectorAll('.tower-floor')].find(f=>f.dataset.session===scrollToSession);if(floor)view.scrollTop=floor.offsetTop-5;scrollToSession=null}trackPosition();
}
function trackTowerArrivals(value){
 const fresh=!value.error&&Date.now()/1000-value.updatedAt<=12;
 if(!fresh){towerAgentIds.clear();towerArrivals.clear();return}
 const live=new Set(value.projects.map(p=>p.id));
 for(const id of towerAgentIds.keys())if(!live.has(id)){towerAgentIds.delete(id);towerArrivals.delete(id)}
 for(const p of value.projects){
  const before=towerAgentIds.get(p.id),current=new Set(),queue=towerArrivals.get(p.id)||[];
  for(const room of p.rooms)occupants(room).forEach((agent,index)=>{
   if(agent.status==='completed')return;current.add(agent.id);
   if(before&&!before.has(agent.id)&&agent.status==='active'&&viewMode==='overview'&&!reducedMotion())queue.push({agent,index,since:performance.now()+queue.length*130});
  });
  towerAgentIds.set(p.id,current);towerArrivals.set(p.id,queue);
 }
}
function drawTowerArrivals(frame){
 const now=performance.now();
 for(const wrapper of $('overview').querySelectorAll('.project-tower')){
  const canvas=wrapper.querySelector('.tower-arrivals'),ctx=canvas.getContext('2d');ctx.clearRect(0,0,220,90);ctx.imageSmoothingEnabled=false;
  const queue=(towerArrivals.get(wrapper.dataset.project)||[]).filter(a=>now-a.since<1500&&!reducedMotion());towerArrivals.set(wrapper.dataset.project,queue);canvas.dataset.arrivals=queue.length;
  const scale=Math.max(.4,parseFloat(wrapper.style.getPropertyValue('--tower-scale'))||1);
  for(const item of queue){const t=Math.max(0,(now-item.since)/1500);if(now<item.since)continue;
   const x=25+85*t,y=85-(7+8*scale)*t,w=20*scale,h=28*scale;
   ctx.save();ctx.globalAlpha=t>.8?(1-t)/.2:Math.min(1,t*8);ctx.translate(x,y+Math.sin(frame*2)*scale);
   ctx.drawImage(images['employee-'+employeeModel(item.agent,item.index)],-w/2,-h,w,h);ctx.restore();
  }
 }
}
function acceptSnapshot(value){if(!value||!Array.isArray(value.projects))return;trackTowerArrivals(value);data=value;freshness();render()}
$('room-grid').onscroll=trackPosition;
let dragStart=null,dragged=false;
$('tower-view').addEventListener('pointerdown',e=>{if(e.button===0){dragStart={x:e.clientX,y:e.clientY};dragged=false}});
document.addEventListener('pointermove',e=>{if(!dragStart)return;if(!(e.buttons&1)){dragStart=null;return}if(Math.hypot(e.clientX-dragStart.x,e.clientY-dragStart.y)>=5){dragStart=null;dragged=true;bridge('drag')}});
document.addEventListener('pointerup',()=>{dragStart=null});
document.addEventListener('pointercancel',()=>{dragStart=null});
$('tower-view').addEventListener('click',e=>{if(dragged){e.preventDefault();e.stopImmediatePropagation();dragged=false}},true);
$('back-to-tower').onclick=()=>{viewMode='overview';render()};
$('back-icon').onclick=$('back-to-tower').onclick;
$('pin').onclick=()=>{const on=$('pin').getAttribute('aria-pressed')!=='true';$('pin').setAttribute('aria-pressed',String(on));$('pin').textContent=on?'◆':'◇';bridge('pin')};$('close').onclick=()=>bridge('close');$('collapse').onclick=()=>{collapsed=!collapsed;document.body.classList.toggle('collapsed',collapsed);$('collapse').textContent=collapsed?'+':'−';bridge('collapse')};$('titlebar').onpointerdown=e=>{if(e.button===0&&!e.target.closest('button'))bridge('drag')};
window.Tower={ready:false,acceptSnapshot};
new ResizeObserver(layoutTowerArt).observe($('overview'));
window.chrome?.webview?.addEventListener('message',e=>acceptSnapshot(e.data));
Promise.all([...Object.keys(window.RoomSkins).flatMap(id=>['room-'+id,'room-'+id+'-glass']),'ambient-clouds','ambient-candle','ambient-glass-mask','book','forge','map','hero-book','hero-forge','hero-map','gothic-interior','employee-scholar','employee-smith','employee-ranger','employee-mage',...['scholar','smith','ranger'].flatMap(group=>[1,2,3].map(n=>'employee-'+group+'-'+n)),'tower-aligned-roof','tower-aligned-floor','tower-aligned-base','tower-aligned-window-mask'].map(name=>new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>{images[name]=img;resolve()};img.onerror=reject;img.src='assets/'+name+'.png'}))).then(()=>{
images['ambient-layer']=document.createElement('canvas');images['ambient-layer'].width=193;images['ambient-layer'].height=224;
const mask=images['tower-aligned-window-mask'],lit=document.createElement('canvas');lit.width=mask.width;lit.height=mask.height;const ctx=lit.getContext('2d');ctx.drawImage(mask,0,0);ctx.globalCompositeOperation='source-in';ctx.fillStyle='#efbf6a';ctx.fillRect(0,0,lit.width,lit.height);images['lit-windows']=lit;
window.Tower.ready=true;render();bridge('ready')}).catch(()=>{$('source').textContent='Не удалось загрузить рисунки комнат'});
setInterval(()=>{lastFrame++;if(lastFrame%7===0)freshness();if(window.Tower.ready){if(viewMode==='rooms')draw(lastFrame);else drawTowerArrivals(lastFrame)}},140);
})();
