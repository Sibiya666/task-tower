const {test}=require('node:test');const assert=require('node:assert/strict');
const {AgentPresence}=require('./web/agent-presence.js');
test('Entry/exit happens once and completed historical agents stay absent',()=>{
 const p=new AgentPresence(),a={id:'a',status:'active'},b={id:'b',status:'active'};
 assert.equal(p.sync('r',[a,{id:'old',status:'completed'}],0).length,1);
 assert.equal(p.sync('r',[a,b],100)[1].motion,'entering');
 assert.equal(p.sync('r',[a,b],300)[1].since,100);
 assert.equal(p.frame('r',1500)[1].motion,'present');
 p.sync('r',[{...a,status:'completed'},b],1600);
 assert.equal(p.frame('r',1700)[0].motion,'exiting');
 p.sync('r',[{...a,status:'completed'},b],1800);
 assert.equal(p.frame('r',3000).length,1);
 assert.equal(p.sync('r',[{...a,status:'completed'},b],3100).length,1);
 assert.equal(p.sync('r',[a,b],3200).find(v=>v.agent.id==='a').motion,'entering');
});
test('Removal exits; reduced motion applies immediately; waiting agents remain',()=>{
 const p=new AgentPresence();p.sync('r',[{id:'a',status:'waiting'}],0);
 assert.equal(p.sync('r',[],100)[0].motion,'exiting');
 assert.equal(p.frame('r',101,true).length,0);
 assert.equal(p.sync('r',[{id:'a',status:'waiting'}],200,true)[0].motion,'present');
});
