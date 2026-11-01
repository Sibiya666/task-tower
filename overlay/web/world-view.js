(function(){'use strict';
const api=window.WorldPolicy;
let settings,visibility;
try{settings=api.normalizeSettings(JSON.parse(localStorage.getItem('world-settings')||'{}'));visibility=new api.WorldVisibility(JSON.parse(localStorage.getItem('world-idle')||'{}'))}catch{settings=api.normalizeSettings();visibility=new api.WorldVisibility()}
let controller=null,currentLight=null,weatherMix=1,lastWeather=settings.weather,frame=0;
const sky=document.createElement('canvas'),weather=document.createElement('canvas');
sky.id='world-sky';weather.id='world-weather';sky.setAttribute('aria-hidden','true');weather.setAttribute('aria-hidden','true');document.body.prepend(sky,weather);
const menu=document.createElement('section');menu.id='world-menu';menu.hidden=true;menu.setAttribute('role','dialog');menu.setAttribute('aria-label','Настройки сцены');document.body.append(menu);
const atlases={};for(const name of ['clouds','rain','fog']){const image=new Image();image.src='assets/world-'+name+'.png';atlases[name]=image}
function save(){try{localStorage.setItem('world-settings',JSON.stringify(settings));localStorage.setItem('world-idle',JSON.stringify(visibility.serialize()))}catch{}}
function label(text){const title=document.createElement('strong');title.textContent=text;menu.append(title)}
function select(title,key,options){const row=document.createElement('label');row.textContent=title;const select=document.createElement('select');select.dataset.setting=key;for(const [value,text] of options){const option=document.createElement('option');option.value=value;option.textContent=text;select.append(option)}select.value=String(settings[key]);select.onchange=()=>{settings[key]=key==='idleMinutes'?Number(select.value):select.value;save();controller?.refresh();};row.append(select);menu.append(row)}
function openMenu(x,y,project=null){
 menu.replaceChildren();label(project?'Этажи проекта':'Настройки мира');
 if(project){
  const expand=document.createElement('button');expand.textContent=controller.isExpanded(project.id)?'Компактная башня':'Показать все этажи на башне';expand.onclick=()=>{controller.expand(project.id);menu.hidden=true};menu.append(expand);
  project.rooms.slice().sort((a,b)=>String(a.id).localeCompare(String(b.id))).reverse().forEach((room,i)=>{const button=document.createElement('button');button.textContent=(project.rooms.length-i)+' · '+(room.title||'Без названия');button.onclick=()=>{controller.open(project.id,room.id);menu.hidden=true};menu.append(button)});
 }else{
  select('Освещение','mode',[['auto','По местному времени'],['day','День'],['night','Ночь']]);
  select('Погода','weather',[['clear','Ясно'],['clouds','Облачно'],['rain','Дождь'],['fog','Туман']]);
  select('Скрывать после простоя','idleMinutes',[[0,'Не скрывать'],[10,'10 минут'],[30,'30 минут'],[60,'1 час']]);
  for(const [key,title] of [['effects','Атмосферные эффекты'],['showHidden','Показывать скрытые башни']]){
   const row=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.checked=settings[key];input.dataset.setting=key;input.onchange=()=>{settings[key]=input.checked;save();controller?.refresh()};row.append(input,document.createTextNode(title));menu.append(row);
  }
 }
 const close=document.createElement('button');close.textContent='Закрыть';close.onclick=()=>{menu.hidden=true};menu.append(close);
 menu.hidden=false;menu.style.left=Math.max(4,Math.min(x,innerWidth-menu.offsetWidth-4))+'px';menu.style.top=Math.max(4,Math.min(y,innerHeight-menu.offsetHeight-4))+'px';menu.querySelector('select,button,input')?.focus();
}
document.addEventListener('contextmenu',e=>{if(e.target.closest('#world-menu'))return;e.preventDefault();openMenu(e.clientX,e.clientY)});
document.addEventListener('pointerdown',e=>{if(!menu.contains(e.target))menu.hidden=true});document.addEventListener('keydown',e=>{if(e.key==='Escape')menu.hidden=true});
function sheet(ctx,image,t,count,columns,w,h,alpha){if(!image.complete||!image.naturalWidth)return;const n=Math.floor(t*6)%count;ctx.globalAlpha=alpha;ctx.drawImage(image,(n%columns)*320,Math.floor(n/columns)*180,320,180,0,0,w,h);ctx.globalAlpha=1}
function draw(){
 if(document.hidden)return;frame++;const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
 const date=new Date(),hour=date.getHours()+date.getMinutes()/60+date.getSeconds()/3600,target=api.daylight(hour,settings.mode);
 currentLight=currentLight===null||reduced?target:currentLight+(target-currentLight)*.08;
 document.documentElement.style.setProperty('--world-brightness',(.82+currentLight*.3).toFixed(2));
 document.documentElement.style.setProperty('--world-saturation',String(.8+currentLight*.2));
 const overview=document.body.classList.contains('overview-mode'),w=Math.ceil(innerWidth/2),h=Math.ceil(innerHeight/2);
 for(const canvas of [sky,weather]){if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h}canvas.getContext('2d').clearRect(0,0,w,h)}
 if(!overview||!settings.effects)return;
 if(reduced){lastWeather=settings.weather;weatherMix=1}else if(lastWeather!==settings.weather){weatherMix=Math.max(0,weatherMix-.15);if(weatherMix===0)lastWeather=settings.weather}else weatherMix=Math.min(1,weatherMix+.08);
 const selected=lastWeather,t=reduced?0:performance.now()/1000,ctx=sky.getContext('2d');ctx.imageSmoothingEnabled=false;
 if(selected!=='clear'){
  ctx.save();ctx.filter=currentLight>.5?'brightness(1.5) saturate(.25)':'none';
  // PixelFX sky at two depths, behind all towers. Transparent margins stay clear.
  sheet(ctx,atlases.clouds,t*.3,72,7,w,h*.56,weatherMix*.38);
  ctx.translate(w*.2,h*.08);sheet(ctx,atlases.clouds,t*.2+3,72,7,w*.8,h*.38,weatherMix*.2);ctx.restore();
 }
 const front=weather.getContext('2d');front.imageSmoothingEnabled=false;
 if(selected==='rain')sheet(front,atlases.rain,t,48,6,w,h,weatherMix*.55);
 if(selected==='fog')sheet(front,atlases.fog,t*.55,72,7,w,h,weatherMix*.38);
}
setInterval(()=>{if(document.hidden)return;draw();if(frame%70===0)controller?.refresh()},140);
window.WorldView={settings,connect(value){controller=value},floorMenu(project,event){event.preventDefault();event.stopPropagation();openMenu(event.clientX||innerWidth-270,event.clientY||50,project)},hidden(project,fresh){const result=visibility.hidden(project,Date.now()/1000,fresh,settings.idleMinutes*60);save();return !settings.showHidden&&result},refresh:draw};
})();
