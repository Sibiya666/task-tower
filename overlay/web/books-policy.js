(function(root){'use strict';
const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
const plain=o=>o!==null&&typeof o==='object'&&!Array.isArray(o)&&(Object.getPrototypeOf(o)===Object.prototype||Object.getPrototypeOf(o)===null);
const bytes=s=>new TextEncoder().encode(s).length;
function fail(){throw new TypeError('Invalid books public data');}
function inspect(v,depth=0){if(depth>24)fail();if(v&&typeof v==='object'){if(!Array.isArray(v)&&!plain(v))fail();for(const k of Object.keys(v)){if(['__proto__','prototype','constructor'].includes(k))fail();inspect(v[k],depth+1);}}else if(typeof v==='number'&&!Number.isFinite(v))fail();else if(['function','symbol','bigint','undefined'].includes(typeof v))fail();}
function text(v,max=32768,nullable=false){if(nullable&&v===null)return null;if(typeof v!=='string'||bytes(v)>max)fail();return v;}
function copyFields(v,fields){const result={};for(const k of fields)if(own(v,k))result[k]=JSON.parse(JSON.stringify(v[k]));return result;}
// Public provenance remains inert data. Unknown metadata never crosses this projection.
const provenanceKeys=new Set(['original_text','session','provider','id','url','event_id','intent','original_kind','requested_relations','parent','sub_issues','milestone','promotion','previous_kind','at','status','remote_attempt','attempt_id','run_id','run_attempt','workflow','repository','issue','number','head','base','head_sha','base_sha','commit','source','evidence','spec','development','test','postmerge','reviewer','verdict','result','phase','stages','name','accepted','pending','project','issue_url','original_source','canonical_source','version']);
for(const k of ['actor','operation','kind','publication_id','ci_run','review','sources','source_sha256'])provenanceKeys.add(k);
const provenanceObjects=new Set(['session','requested_relations','promotion','remote_attempt','review','stages','spec','development','test','postmerge','parent','milestone','evidence']);
const provenanceLists=new Set(['sub_issues']);
function provenance(v){
 if(!plain(v))fail();const result={};
 for(const k of Object.keys(v)){
  if(!provenanceKeys.has(k))continue;const value=v[k];
  if(k==='source_sha256'){
   result[k]=text(value,64);if(!/^[a-f0-9]{64}$/.test(value))fail();
  }else if(k==='sources'){
   if(!Array.isArray(value)||value.length>100)fail();
   result[k]=value.map(x=>{
    text(x,8192);if(/[\\\x00-\x20\x7f]/.test(x))fail();
    let url;try{url=new URL(x);}catch{fail();}
    if(url.protocol!=='https:'||!url.hostname||url.username||url.password)fail();
    return x;
   });
  }else if(provenanceObjects.has(k)){
   if(value===null)result[k]=null;
   else if(plain(value))result[k]=provenance(value);
   else if(typeof value==='string')result[k]=text(value,32768);
   else fail();
  }else if(provenanceLists.has(k)){
   if(!Array.isArray(value)||value.length>100)fail();result[k]=value.map(x=>plain(x)?provenance(x):text(x,2048));
  }else if(typeof value==='string')result[k]=text(value,32768);
  else if(value===null||typeof value==='boolean'||(typeof value==='number'&&Number.isSafeInteger(value)))result[k]=value;
  else fail();
 }
 return result;
}
const issueId=/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+#[1-9]\d*$/;
function positive(v){if(!Number.isSafeInteger(v)||v<1)fail();return v;}
const repositoryId=/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;
const beadIdentity=/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+:beads:[A-Za-z0-9][A-Za-z0-9_.-]{0,99}:[A-Za-z0-9][A-Za-z0-9_.-]{0,199}$/;
function resultEvidence(v){
 if(!plain(v))fail();
 if(['missing','unavailable'].includes(v.status)&&Object.keys(v).length===1)return {status:v.status};
 if(v.status!=='recorded'||Object.keys(v).length!==4||!['status','version','pr','main_sha'].every(k=>own(v,k))||v.version!==1||typeof v.main_sha!=='string'||! /^[a-f0-9]{40}$/.test(v.main_sha))fail();
 return {status:'recorded',version:1,pr:positive(v.pr),main_sha:v.main_sha};
}
function qualified(v){text(v,2048);if(beadIdentity.test(v))return v;if(!issueId.test(v)||!Number.isSafeInteger(Number(v.slice(v.lastIndexOf('#')+1))))fail();return v;}
function relation(v,type){
 if(v===undefined)return {status:'unavailable'};
 if(v===null){if(type==='child')fail();return null;}
 if(!plain(v))fail();
 if(v.status==='unavailable')return {status:'unavailable'};
 const result={};
 if(type==='milestone'){
  if(typeof v.id==='number')result.id=positive(v.id);else result.id=text(v.id,2048);
  if(own(v,'number'))result.number=positive(v.number);
  if(own(v,'title'))result.title=text(v.title,8192);
 }else result.id=qualified(v.id);
 if(own(v,'source'))result.source=text(v.source,8192);
 return result;
}
function entry(v){
 if(!plain(v))fail();
 if(own(v,'result_evidence')&&(v.source_kind!=='beads'||v.book!=='tasks'))fail();
 const e={id:text(v.id,2048),project:text(v.project,2048),book:text(v.book,32),repository:text(v.repository,2048)};
 if(!repositoryId.test(e.repository)||!['ideas','tasks','library'].includes(e.book))fail();
 // Every copied scalar is validated before assignment; structured fields use dedicated projections.
 for(const k of ['title','status','source','created_at','updated_at'])if(own(v,k))e[k]=text(v[k],8192,k==='source'&&(v.source_kind==='beads'||(v.book==='library'&&v.available===false)));
 if(e.book==='library'){
  e.path=text(v.path,8192);e.commit=text(v.commit,40);e.artifact_state=text(v.artifact_state,32);
  if(!/^[a-f0-9]{40}$/.test(e.commit)||e.id!==e.repository+':'+e.path+'@'+e.commit||!e.path.toLowerCase().endsWith('.md')||e.path.split('/').some(p=>!p||p==='.'||p==='..')||/[\\\x00-\x1f\x7f-\x9f]/.test(e.path)||!['working','accepted','superseded','unknown'].includes(e.artifact_state)||typeof v.available!=='boolean')fail();
  e.available=v.available;e.status='source';
  if(own(v,'declaration_source'))e.declaration_source=text(v.declaration_source,8192,true);
  if(own(v,'issues')){if(!Array.isArray(v.issues)||v.issues.length>10000)fail();e.issues=v.issues.map(qualified);}
  if(own(v,'milestone')){if(v.milestone===null)e.milestone=null;else{if(!plain(v.milestone))fail();const repository=text(v.milestone.repository,2048);if(!repositoryId.test(repository))fail();e.milestone={repository,number:positive(v.milestone.number)};}}
 }else{
  if(v.source_kind==='beads'){
   e.source_kind='beads';e.bead_id=text(v.bead_id,200);
   if(e.book!=='tasks'||e.source!==null||!beadIdentity.test(e.id)||e.id!==e.repository+':beads:'+e.project+':'+e.bead_id||v.verification!=='not_required'||e.status==='done')fail();
   if(own(v,'assignee'))e.assignee=text(v.assignee,256);
   e.result_evidence=own(v,'result_evidence')?resultEvidence(v.result_evidence):{status:'missing'};
  }else{qualified(e.id);e.number=positive(v.number);if(e.id!==e.repository+'#'+e.number)fail();}
  e.verification=text(v.verification,32);if(!['pending','verified','unverified','not_required'].includes(e.verification))fail();
  if(own(v,'remote_state'))e.remote_state=text(v.remote_state,32,true);
  if(own(v,'description'))e.description=text(v.description,32768);
  if(own(v,'phase')){e.phase=text(v.phase,1024,true);if(e.phase!==null&&Array.from(e.phase).length>256)fail();}
  for(const k of ['blockers','results'])if(own(v,k)){if(!Array.isArray(v[k])||v[k].length>100)fail();e[k]=v[k].map(x=>{text(x,k==='blockers'?1024:8192);if(k==='blockers'&&Array.from(x).length>256)fail();return x;});}
  for(const k of ['history','migrations'])if(own(v,k)){if(!Array.isArray(v[k])||v[k].length>100||v[k].some(x=>!plain(x)))fail();e[k]=v[k].map(provenance);}
  if(own(v,'capture')){if(!plain(v.capture))fail();e.capture=provenance(v.capture);}
  if(own(v,'blocked_by')){if(!Array.isArray(v.blocked_by)||v.blocked_by.length>100)fail();e.blocked_by=v.blocked_by.map(qualified);}
  for(const k of ['remote_attempt','stages'])if(own(v,k))e[k]=provenance(v[k]);
  if(e.status==='done'&&e.verification!=='verified')e.status='unknown';
  const r=v.relationships;
  if(r===undefined||r===null)e.relationships={parent:{status:'unavailable'},sub_issues:{status:'unavailable'},milestone:{status:'unavailable'}};
  else{
   if(!plain(r))fail();const children=r.sub_issues===undefined?{status:'unavailable'}:r.sub_issues;
   if(!Array.isArray(children)&&(!plain(children)||children.status!=='unavailable'))fail();
   if(Array.isArray(children)&&children.length>10000)fail();
   e.relationships={parent:relation(r.parent,'parent'),milestone:relation(r.milestone,'milestone'),sub_issues:Array.isArray(children)?children.map(x=>relation(x,'child')):{status:'unavailable'}};
  }
 }
 return e;
}
function isStale(e,nowMs=Date.now()){const time=Date.parse(e?.fetched_at);return e?.stale===true||['loading','unavailable','unconfigured'].includes(e?.state)||!Number.isFinite(time)||time>nowMs||nowMs-time>=300000;}
function normalizeEnvelope(v,nowMs=Date.now()){inspect(v);if(!plain(v)||bytes(JSON.stringify(v))>8*1024*1024||v.kind!=='books'||v.version!==1||!Number.isSafeInteger(v.sequence)||v.sequence<1||typeof v.final!=='boolean'||!['ready','partial','unavailable','unconfigured','loading'].includes(v.state)||!Array.isArray(v.entries)||v.entries.length>10000||!Array.isArray(v.errors)||v.errors.length>10000||(v.fetched_at!==null&&typeof v.fetched_at!=='string'))fail();const e=copyFields(v,['kind','version','sequence','final','state','fetched_at']);e.errors=v.errors.map(x=>{if(!plain(x))fail();return {project:text(x.project,2048),source:text(x.source,8192),error:text(x.error,8192)};});e.entries=v.entries.map(entry);if(['loading','unavailable'].includes(e.state))for(const x of e.entries)if(x.book!=='library'&&x.source_kind!=='beads'){x.verification='pending';if(x.status==='done')x.status='unknown';}e.stale=isStale(v,nowMs);return e;}
function compare(a,b){const ai=a.id.match(/^(.*)#(\d+)$/),bi=b.id.match(/^(.*)#(\d+)$/);if(ai&&bi){const repo=ai[1].localeCompare(bi[1],'en');if(repo)return repo;return Number(ai[2])-Number(bi[2]);}return a.id.localeCompare(b.id,'en');}
function buildRows(entries,options={}){
 const {book,project,status,grouping='stage',expanded=[]}=options;const expand=new Set(expanded);const all=new Map();for(const e of [...entries].sort(compare))if(!all.has(e.id))all.set(e.id,e);
 const list=[...all.values()].filter(e=>(!book||book==='all'||e.book===book)&&(!project||project==='all'||e.project===project)&&(!status||status==='all'||e.status===status));const visible=new Map(list.map(e=>[e.id,e]));const rows=[],emitted=new Set();
 const ref=(r,owner,reason)=>rows.push({kind:'reference',id:r.id,source:r.source||all.get(r.id)?.source,owner,reason});
 const warning=(id,reason)=>rows.push({kind:'warning',id:`${id}:${reason}`,owner:id,reason});
 function emit(e,depth=0){if(emitted.has(e.id))return;emitted.add(e.id);const r=e.relationships||{},children=Array.isArray(r.sub_issues)?r.sub_issues:[];const ids=new Set(children.map(c=>c.id));for(const x of all.values())if(x.relationships?.parent?.id===e.id)ids.add(x.id);const loaded=[...ids].map(id=>all.get(id)).filter(Boolean);const progress={accepted:loaded.filter(x=>x.status==='done'&&x.verification==='verified').length,closed:loaded.filter(x=>x.remote_state==='closed').length,loaded:loaded.length,unresolved:[...ids].filter(id=>!all.has(id)).length+(r.sub_issues?.status==='unavailable'?1:0)};rows.push({kind:'record',id:e.id,entry:e,depth,progress,expandable:ids.size>0||r.sub_issues?.status==='unavailable'});
 if(e.book!=='tasks')return;
 if(r.parent?.status==='unavailable')warning(e.id,'parent-unavailable');else if(r.parent?.id&&!visible.has(r.parent.id))ref(r.parent,e.id,all.has(r.parent.id)?'parent-filtered':'parent-unloaded');else if(grouping!=='features'&&r.parent?.id)ref(r.parent,e.id,'parent');
 if(r.sub_issues?.status==='unavailable')warning(e.id,'children-unavailable');if(r.milestone?.status==='unavailable')warning(e.id,'milestone-unavailable');
 const seen=new Set([e.id]);let ancestor=r.parent?.id;while(ancestor){if(seen.has(ancestor)){warning(e.id,'relationship-cycle');break;}seen.add(ancestor);ancestor=all.get(ancestor)?.relationships?.parent?.id;}
 if(expand.has(e.id)){for(const id of [...ids].map(id=>({id})).sort(compare).map(x=>x.id)){const child=visible.get(id);if(!child)ref(children.find(x=>x.id===id)||{id},e.id,all.has(id)?'child-filtered':'child-unloaded');else if(grouping==='features'&&!emitted.has(id))emit(child,depth+1);else if(grouping!=='features')ref({id,source:child.source},e.id,'child');}}
 }
 if(grouping==='features'){for(const e of list)if(!visible.has(e.relationships?.parent?.id))emit(e);for(const e of list){if(emitted.has(e.id))continue;let id=e.id,seen=new Set();while(visible.has(id)&&!seen.has(id)){seen.add(id);id=visible.get(id).relationships?.parent?.id;}if(seen.has(id))emit(e);}}
 else {let group;const grouped=list.map(e=>{const m=e.relationships?.milestone;const key=e.book==='tasks'?(m?.status==='unavailable'?'~unavailable':m?String(m.id):'~unassigned'):e.book;return {e,key,title:m?.title||key};}).sort((a,b)=>a.key.localeCompare(b.key,'en')||compare(a.e,b.e));for(const x of grouped){if(x.key!==group){group=x.key;rows.push({kind:'group',id:group,title:x.title});}emit(x.e);}}
 return rows;
}
function pageRows(rows,page,pageSize=3){
 if(!Number.isInteger(pageSize)||pageSize<1||pageSize>3)throw new RangeError('Page size must be 1..3');
 const records=rows.filter(r=>r.kind==='record'),total=records.length,pages=Math.max(1,Math.ceil(total/pageSize));
 page=Math.max(0,Math.min(pages-1,Number.isFinite(page)?Math.trunc(page):0));
 const attachments=new Map(),groups=new Map();let group=null;
 for(const row of rows){
  if(row.kind==='group')group=row;
  else if(row.kind==='record')groups.set(row.id,group);
  else if(row.owner){if(!attachments.has(row.owner))attachments.set(row.owner,[]);attachments.get(row.owner).push(row);}
 }
 const result=[];let lastGroup=null;
 for(const record of records.slice(page*pageSize,(page+1)*pageSize)){
  const heading=groups.get(record.id);if(heading&&heading!==lastGroup){result.push(heading);lastGroup=heading;}
  result.push(record,...(attachments.get(record.id)||[]));
 }
 return {rows:result,page,pages,total};
}
const api={normalizeEnvelope,buildRows,pageRows,isStale};if(typeof module!=='undefined')module.exports=api;else root.BooksPolicy=api;
})(globalThis);
