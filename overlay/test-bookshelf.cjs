const {test}=require('node:test');const assert=require('node:assert/strict');const path=require('node:path');
const {chromium}=require('C:/Users/sibiya666/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
test('Floor shelf opens three spine books, parchment corners paginate and focus returns',async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{const p=await browser.newPage({viewport:{width:340,height:300}}),errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.goto('file:///'+path.join(__dirname,'web/index.html').replaceAll('\\','/'));await p.waitForFunction(()=>Tower.ready);
 await p.evaluate(()=>Tower.acceptSnapshot({updatedAt:Date.now()/1000,projects:[{id:'p',name:'Project',rooms:[{id:'r',title:'Floor',status:'active',agents:[]}]}]}));
 assert.equal(await p.locator('#floor-bookshelf').isVisible(),false);
 await p.locator('.overview-floor').evaluate(e=>e.click());
 assert.equal(await p.locator('#floor-bookshelf button').count(),3);assert.equal(await p.locator('#floor-bookshelf').isVisible(),true);
 await p.screenshot({path:path.join(__dirname,'runtime/bookshelf-floor-fixture.png'),omitBackground:true});
 await p.evaluate(()=>BooksView.acceptSnapshot({kind:'books',version:1,sequence:1,final:true,state:'ready',fetched_at:new Date().toISOString(),entries:Array.from({length:7},(_,i)=>({id:'o/r#'+(i+1),number:i+1,verification:'pending',source:'https://github.com/o/r/issues/'+(i+1),repository:'o/r',project:'p',book:'tasks',title:'Задача '+(i+1),status:'active',relationships:{parent:null,sub_issues:[],milestone:null}})),errors:[]}));
 await p.getByRole('button',{name:'Открыть книгу «Задачи»',exact:true}).click();
 assert.equal(await p.locator('[data-filter=book]').inputValue(),'tasks');assert.equal(await p.locator('[data-filter=project]').inputValue(),'p');
 assert.equal(await p.locator('.book-page').count(),2);assert.equal(await p.locator('.books-card').count(),3);
 assert.equal(await p.getByRole('button',{name:'Назад',exact:true}).isDisabled(),true);
 await p.getByRole('button',{name:'Далее',exact:true}).click();assert.match(await p.locator('.books-card').first().textContent(),/Задача 4/);
 await p.getByRole('button',{name:'Назад',exact:true}).click();assert.match(await p.locator('.books-card').first().textContent(),/Задача 1/);
 await p.evaluate(()=>document.fonts.ready);assert.equal(await p.evaluate(()=>document.fonts.check('10px "Tower Pixel"','Книги')),true);
 for(const size of [{width:340,height:300},{width:500,height:400}]){await p.setViewportSize(size);assert.equal(await p.locator('#books-dialog').evaluate(e=>e.scrollWidth<=e.clientWidth),true);for(const corner of ['.book-turn-prev','.book-turn-next']){const box=await p.locator(corner).boundingBox();assert.ok(box.y+box.height<=size.height&&box.x>=0&&box.x+box.width<=size.width)}}
 await p.screenshot({path:path.join(__dirname,'runtime/bookshelf-parchment-fixture.png'),omitBackground:true});
 await p.keyboard.press('Escape');assert.equal(await p.evaluate(()=>document.activeElement.dataset.book),'tasks');
 await p.getByRole('button',{name:'Открыть книгу «Идеи»',exact:true}).click();assert.equal(await p.locator('[data-filter=book]').inputValue(),'ideas');await p.keyboard.press('Escape');
 await p.locator('#back-icon').click();assert.equal(await p.locator('#floor-bookshelf').isVisible(),false);assert.deepEqual(errors,[]);
 }finally{await browser.close()}
});

test('Floor project scope never falls back to unrelated records and explicit mapping survives reopen',async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{const p=await browser.newPage({viewport:{width:500,height:400}});await p.goto('file:///'+path.join(__dirname,'web/index.html').replaceAll('\\','/'));
 const frame=entries=>({kind:'books',version:1,sequence:1,final:true,state:'ready',fetched_at:new Date().toISOString(),errors:[],entries});
 const record=(id,project)=>({id:'o/r#'+id,number:id,repository:'o/r',project,book:'tasks',title:project,status:'active',verification:'pending',source:'https://github.com/o/r/issues/'+id,relationships:{parent:null,sub_issues:[],milestone:null}});
 const entries=[record(1,'configured-project'),record(2,'other-project')];await p.evaluate(v=>BooksView.acceptSnapshot(v),frame(entries));
 await p.evaluate(()=>BooksView.open('codex-project-uuid','tasks'));assert.equal(await p.locator('.books-card').count(),0);assert.equal(await p.locator('[data-filter=project]').inputValue(),'codex-project-uuid');
 await p.evaluate(v=>BooksView.acceptSnapshot(v),frame([entries[1]]));assert.equal(await p.locator('.books-card').count(),0);
 await p.evaluate(v=>BooksView.acceptSnapshot(v),frame(entries));await p.locator('[data-filter=project]').selectOption('configured-project');assert.equal(await p.locator('.books-card').count(),1);
 await p.evaluate(v=>BooksView.acceptSnapshot(v),frame([]));assert.equal(await p.locator('[data-filter=project]').inputValue(),'configured-project');
 await p.evaluate(v=>BooksView.acceptSnapshot(v),frame(entries));assert.equal(await p.locator('.books-card').count(),1);
 await p.keyboard.press('Escape');await p.evaluate(()=>BooksView.open('codex-project-uuid','tasks'));assert.equal(await p.locator('[data-filter=project]').inputValue(),'configured-project');assert.equal(await p.locator('.books-card').count(),1);
 }finally{await browser.close()}
});
