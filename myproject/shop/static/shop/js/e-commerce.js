// CART
let cart = [];
const CART_ENDPOINTS = { detail:'/cart/', add:'/cart/add/', update:'/cart/update/', remove:'/cart/remove/' };

function formatPrice(n){ return '$' + Number(n).toLocaleString(); }

function getCookie(name){
  const v = `; ${document.cookie}`, p = v.split(`; ${name}=`);
  return p.length === 2 ? p.pop().split(';').shift() : '';
}

function applyCartData(data){
  cart = data.items || [];
  const total = data.total_qty ?? cart.reduce((s,i)=>s+i.qty,0);
  const subtotal = data.subtotal ?? cart.reduce((s,i)=>s+i.price*i.qty,0);
  document.getElementById('cartCount').textContent = total;
  document.getElementById('cartTotal').textContent = formatPrice(subtotal);
  document.getElementById('cartFooter').style.display = cart.length ? 'block' : 'none';
  renderCartItems();
}

async function fetchCart(){
  try{
    const res = await fetch(CART_ENDPOINTS.detail,{headers:{'X-Requested-With':'fetch'}});
    if(res.ok) applyCartData(await res.json());
  }catch(e){}
}

async function postCart(url, payload){
  try{
    const res = await fetch(url,{
      method:'POST',
      headers:{'Content-Type':'application/json','X-CSRFToken':getCookie('csrftoken'),'X-Requested-With':'fetch'},
      body:JSON.stringify(payload||{})
    });
    if(res.ok) applyCartData(await res.json());
  }catch(e){}
}

function addToCart(id){
  const p = PRODUCTS.find(x=>x.id===id);
  postCart(CART_ENDPOINTS.add,{product_id:id,quantity:1});
  if(p) showToast(p.name+' added to cart');
}
function removeFromCart(id){ postCart(CART_ENDPOINTS.remove,{product_id:id}); }
function changeQty(id,delta){
  const item = cart.find(x=>x.id===id);
  postCart(CART_ENDPOINTS.update,{product_id:id,quantity:(item?item.qty:0)+delta});
}

function renderCartItems(){
  const el = document.getElementById('cartItems');
  if(!cart.length){
    el.innerHTML = `<div class="cart-empty"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/></svg><p>Your cart is empty</p></div>`;
    return;
  }
  el.innerHTML = cart.map(item=>`
    <div class="cart-item">
      <img class="cart-item-img" src="${item.img}" alt="${item.name}"/>
      <div class="cart-item-details">
        <p class="cart-item-brand">${item.brand}</p>
        <p class="cart-item-name">${item.name}</p>
        <p class="cart-item-price">${formatPrice(item.price)}</p>
        <div class="cart-qty">
          <button data-action="qty" data-id="${item.id}" data-delta="-1">−</button>
          <span>${item.qty}</span>
          <button data-action="qty" data-id="${item.id}" data-delta="1">+</button>
        </div>
        <button class="cart-item-remove" data-action="remove" data-id="${item.id}">Remove</button>
      </div>
    </div>`).join('');
}

function openCart(){ document.getElementById('cartDrawer').classList.add('open'); document.getElementById('cartOverlay').classList.add('open'); fetchCart(); }
function closeCart(){ document.getElementById('cartDrawer').classList.remove('open'); document.getElementById('cartOverlay').classList.remove('open'); }

// SEARCH
function openSearch(){
  document.getElementById('searchOverlay').classList.add('open');
  document.getElementById('searchBackdrop').classList.add('open');
  setTimeout(()=>document.getElementById('searchInput').focus(),120);
}
function closeSearch(){
  document.getElementById('searchOverlay').classList.remove('open');
  document.getElementById('searchBackdrop').classList.remove('open');
  document.getElementById('searchInput').value='';
  document.getElementById('searchResults').classList.remove('show');
  document.getElementById('searchPopular').style.display='';
}

document.getElementById('searchInput').addEventListener('input',function(){
  const q = this.value.trim().toLowerCase();
  const res = document.getElementById('searchResults');
  const list = document.getElementById('searchResultsList');
  const popular = document.getElementById('searchPopular');
  if(!q){ res.classList.remove('show'); popular.style.display=''; return; }
  popular.style.display='none';
  const matches = PRODUCTS.filter(p=>
    p.name.toLowerCase().includes(q)||p.cat.toLowerCase().includes(q)||p.brand.toLowerCase().includes(q)
  );
  list.innerHTML = matches.length
    ? matches.map(p=>`
        <a href="/product/${p.id}/" class="search-result-item">
          <img src="${p.img}" alt="${p.name}"/>
          <div class="search-result-info">
            <p class="search-result-cat">${p.cat}</p>
            <p class="search-result-name">${p.name}</p>
            <p class="search-result-price">${formatPrice(p.price)}</p>
          </div>
        </a>`).join('')
    : `<div class="search-no-results">No products found for "${this.value}"</div>`;
  res.classList.add('show');
});

// TOAST
let toastTimer;
function showToast(msg){
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(()=>t.classList.remove('show'),2200);
}

// PAGE NAVIGATION
function showPage(name, filter){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.getElementById('page-'+name).classList.add('active');
  window.scrollTo(0,0);
  document.querySelectorAll('.nav-tab-link').forEach(l=>l.classList.remove('active'));
  if(name==='all'){
    document.getElementById('allTab').classList.add('active');
    filterProducts(filter||'All');
  }
  observeReveal();
}

// MODAL


// FILTER — hide/show server-rendered cards by data-cat
function filterProducts(cat){
  document.querySelectorAll('.filter-btn').forEach(b=>b.classList.toggle('active',b.dataset.filter===cat));
  const cards = document.querySelectorAll('#allProductsGrid .prod-card');
  let visible = 0;
  cards.forEach(card=>{
    const match = cat==='All' || card.dataset.cat===cat;
    card.classList.toggle('visible', match);
    if(match) visible++;
  });
  document.getElementById('allProductsCount').textContent =
    `Showing ${visible} piece${visible!==1?'s':''}`;
}

// SCROLL REVEAL
const revealObserver = new IntersectionObserver(entries=>{
  entries.forEach(e=>{ if(e.isIntersecting){ e.target.classList.add('visible'); revealObserver.unobserve(e.target); }});
},{threshold:0.1});

function observeReveal(){
  document.querySelectorAll('.reveal:not(.visible)').forEach(el=>revealObserver.observe(el));
}

// DELEGATED EVENTS
document.addEventListener('click',function(e){
  const actionEl = e.target.closest('[data-action]');
  if(actionEl){
    const action = actionEl.dataset.action;
    const id = actionEl.dataset.id ? parseInt(actionEl.dataset.id) : null;
    if(action==='open-modal'){ if(id) openModal(id); return; }
    if(action==='add-to-cart'){ e.stopPropagation(); addToCart(id); return; }
    if(action==='modal-add'){ addToCart(id); closeModal(); return; }
    if(action==='remove'){ removeFromCart(id); return; }
    if(action==='qty'){ changeQty(id,parseInt(actionEl.dataset.delta)); return; }
    if(action==='thumb'){ const m=document.getElementById('modalMainImage'); if(m) m.src=actionEl.dataset.src; return; }
    if(action==='search-select'){
      if(id){ openModal(id); closeSearch(); return; }
      closeSearch(); showPage('all','All'); return;
    }
  }
  const pageEl = e.target.closest('[data-page]');
  if(pageEl){ showPage(pageEl.dataset.page, pageEl.dataset.filter||'All'); return; }
  const filterBtn = e.target.closest('.filter-btn[data-filter]');
  if(filterBtn){ filterProducts(filterBtn.dataset.filter); return; }
});

// WIRING
document.getElementById('navLogo').addEventListener('click',()=>showPage('home'));
document.getElementById('searchOpenBtn').addEventListener('click',openSearch);
document.getElementById('searchCloseBtn').addEventListener('click',closeSearch);
document.getElementById('searchBackdrop').addEventListener('click',closeSearch);
document.getElementById('cartOpenBtn').addEventListener('click',openCart);
document.getElementById('cartCloseBtn').addEventListener('click',closeCart);
document.getElementById('cartOverlay').addEventListener('click',closeCart);
document.getElementById('modalBackdrop').addEventListener('click',closeModal);
document.getElementById('modalCloseBtn').addEventListener('click',closeModal);

document.querySelectorAll('.search-tag[data-search]').forEach(btn=>{
  btn.addEventListener('click',()=>{
    document.getElementById('searchInput').value=btn.dataset.search;
    document.getElementById('searchInput').dispatchEvent(new Event('input'));
  });
});

document.addEventListener('keydown',e=>{ if(e.key==='Escape'){ closeSearch(); closeModal(); }});

// INIT
filterProducts('All');
renderCartItems();
observeReveal();

const searchInput = document.getElementById("searchInput");
const searchForm = document.getElementById("searchForm");

searchInput.addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        e.preventDefault(); // stop overlay behavior
        
        const query = searchInput.value.trim();
        if (query) {
            window.location.href = `/search/?q=${encodeURIComponent(query)}`;
        }
    }
});