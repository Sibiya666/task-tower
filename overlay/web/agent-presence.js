(function(root){'use strict';
class AgentPresence{
 constructor(){this.rooms=new Map();this.duration=1200}
 sync(id,agents,now,reduced=false){
  const first=!this.rooms.has(id),items=this.rooms.get(id)||new Map();this.rooms.set(id,items);
  const live=new Set();
  agents.forEach((agent,index)=>{
   const key=String(agent.id);live.add(key);let item=items.get(key);
   if(agent.status==='completed'){
    if(item&&item.motion!=='exiting'){item.motion='exiting';item.since=now}
    return;
   }
   if(!item){item={agent,index,motion:first||reduced?'present':'entering',since:now};items.set(key,item)}
   else{item.agent=agent;item.index=index;if(item.motion==='exiting'){item.motion=reduced?'present':'entering';item.since=now}}
  });
  for(const [key,item] of items)if(!live.has(key)&&item.motion!=='exiting'){item.motion='exiting';item.since=now}
  return this.frame(id,now,reduced);
 }
 frame(id,now,reduced=false){
  const items=this.rooms.get(id);if(!items)return [];
  for(const [key,item] of items){
   item.progress=reduced?1:Math.min(1,Math.max(0,(now-item.since)/this.duration));
   if(item.motion==='exiting'&&item.progress>=1)items.delete(key);
   else if(item.motion==='entering'&&item.progress>=1)item.motion='present';
  }
  return [...items.values()];
 }
}
if(typeof module!=='undefined')module.exports={AgentPresence};else root.AgentPresence=AgentPresence;
})(globalThis);
