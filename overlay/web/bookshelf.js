(function(){'use strict';
const shelf=document.createElement('aside');shelf.id='floor-bookshelf';shelf.hidden=true;shelf.setAttribute('aria-label','Книжная полка');
for(const [id,label,mark] of [['ideas','Идеи','✦'],['tasks','Задачи','◆'],['library','Библиотека проекта','▤']]){
 const book=document.createElement('button');book.type='button';book.dataset.book=id;book.setAttribute('aria-label','Открыть книгу «'+label+'»');book.title=label;
 const emblem=document.createElement('span');emblem.className='spine-emblem';emblem.textContent=mark;
 const name=document.createElement('span');name.className='spine-title';name.textContent=id==='library'?'Библиотека':label;book.append(emblem,name);
 book.onclick=()=>window.BooksView.open(shelf.dataset.project,id);shelf.append(book);
}
document.getElementById('tower-view').append(shelf);
window.Bookshelf={show(projectId,visible){shelf.hidden=!visible;shelf.dataset.project=projectId||''}};
})();
