function formatPrice(value) {
  return "\u20B9" + Number(value).toLocaleString();
}

function addToGuestCart(id) {
  const cart = JSON.parse(localStorage.getItem("guest_cart") || "{}");
  cart[id] = (cart[id] || 0) + 1;
  localStorage.setItem("guest_cart", JSON.stringify(cart));
  updateCartBadge();
}

function getGuestCartCount() {
  const cart = JSON.parse(localStorage.getItem("guest_cart") || "{}");
  return Object.values(cart).reduce((total, quantity) => total + Number(quantity || 0), 0);
}

function setCartBadge(count) {
  const badge = document.getElementById("cartCount");
  if (!badge) return;

  badge.textContent = count > 99 ? "99+" : String(count);
  badge.hidden = count <= 0;
}

async function updateCartBadge() {
  try {
    const response = await fetch("/cart/session/count/");

    if (!response.ok) {
      setCartBadge(0);
      return;
    }

    const data = await response.json();
    setCartBadge(data.count || 0);
  } catch {
    setCartBadge(0);
  }
}

function getCookie(name) {
  const cookies = document.cookie ? document.cookie.split(";") : [];

  for (let cookie of cookies) {
    cookie = cookie.trim();

    if (cookie.startsWith(name + "=")) {
      return decodeURIComponent(cookie.substring(name.length + 1));
    }
  }

  return null;
}

async function addToCart(id) {
  try {
    const response = await fetch(`/cart/session/add/${id}/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCookie("csrftoken"),
        "Content-Type": "application/json"
      }
    });

    if (response.status === 401) {
      window.location.href = "/login/?next=/cart/";
      return;
    }

    if (response.ok) {
      const product = PRODUCTS.find(item => item.id === id);
      showToast(`${product ? product.name : "Product"} added to cart`);
      updateCartBadge();
      return;
    }

    showToast("Unable to add this product");
  } catch {
    showToast("Unable to reach the server");
  }
}

function openSearch() {
  document.getElementById("searchOverlay").classList.add("open");
  document.getElementById("searchBackdrop").classList.add("open");
  setTimeout(() => document.getElementById("searchInput").focus(), 120);
}

function closeSearch() {
  document.getElementById("searchOverlay").classList.remove("open");
  document.getElementById("searchBackdrop").classList.remove("open");
  document.getElementById("searchInput").value = "";
  document.getElementById("searchResults").classList.remove("show");
  document.getElementById("searchPopular").style.display = "";
}

document.getElementById("searchInput").addEventListener("input", function () {
  const query = this.value.trim().toLowerCase();
  const results = document.getElementById("searchResults");
  const list = document.getElementById("searchResultsList");
  const popular = document.getElementById("searchPopular");

  if (!query) {
    results.classList.remove("show");
    popular.style.display = "";
    return;
  }

  popular.style.display = "none";
  const matches = PRODUCTS.filter(product =>
    product.name.toLowerCase().includes(query) ||
    product.cat.toLowerCase().includes(query) ||
    product.brand.toLowerCase().includes(query)
  );

  list.innerHTML = matches.length
    ? matches.map(product => `
        <a href="/product/${product.id}/" class="search-result-item">
          <img src="${product.img}" alt="${product.name}"/>
          <div class="search-result-info">
            <p class="search-result-cat">${product.cat}</p>
            <p class="search-result-name">${product.name}</p>
            <p class="search-result-price">${formatPrice(product.price)}</p>
          </div>
        </a>`).join("")
    : `<div class="search-no-results">No products found for "${this.value}"</div>`;

  results.classList.add("show");
});

let toastTimer;

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2200);
}

function showPage(name, filter) {
  document.querySelectorAll(".page").forEach(page => page.classList.remove("active"));
  document.getElementById(`page-${name}`).classList.add("active");
  const categoryNavRow = document.querySelector(".category-nav-row");
  const mobileMenuToggle = document.querySelector(".mobile-menu-toggle");
  const mobileCategoryMenu = document.getElementById("mobileCategoryMenu");
  const isLandingPage = name === "home";

  if (categoryNavRow) categoryNavRow.hidden = !isLandingPage;
  if (mobileMenuToggle) mobileMenuToggle.hidden = !isLandingPage;
  if (!isLandingPage && mobileCategoryMenu) mobileCategoryMenu.classList.remove("open");
  window.scrollTo(0, 0);
  document.querySelectorAll(".nav-tab-link").forEach(link => link.classList.remove("active"));

  if (name === "all") {
    document.getElementById("allTab").classList.add("active");
    filterProducts(filter || "All");
  }

  observeReveal();
}

function openModal(id) {
  window.location.href = `/product/${id}/`;
}

function closeModal() {
  document.getElementById("productModal").classList.remove("open");
  document.getElementById("modalBackdrop").classList.remove("open");
}

const megaNav = document.querySelector("[data-mega-nav]");
const categoryMenuItems = document.querySelectorAll("[data-category-menu]");
const mobileMenuToggle = document.querySelector(".mobile-menu-toggle");
const mobileCategoryMenu = document.getElementById("mobileCategoryMenu");
let megaCloseTimer;

function closeAllCategoryMenus(exceptItem) {
  categoryMenuItems.forEach(item => {
    if (item === exceptItem) return;
    item.classList.remove("menu-open");
    const link = item.querySelector(".category-nav-link");
    if (link) link.setAttribute("aria-expanded", "false");
  });
}

function openCategoryMenu(item) {
  if (!item || window.matchMedia("(max-width: 768px)").matches) return;
  clearTimeout(megaCloseTimer);
  closeAllCategoryMenus(item);
  item.classList.add("menu-open");
  const link = item.querySelector(".category-nav-link");
  if (link) link.setAttribute("aria-expanded", "true");
}

function closeCategoryMenu(item, delay = 140) {
  if (!item) return;
  clearTimeout(megaCloseTimer);
  megaCloseTimer = setTimeout(() => {
    item.classList.remove("menu-open");
    const link = item.querySelector(".category-nav-link");
    if (link) link.setAttribute("aria-expanded", "false");
  }, delay);
}

categoryMenuItems.forEach(item => {
  item.addEventListener("mouseenter", () => openCategoryMenu(item));
  item.addEventListener("mouseleave", () => closeCategoryMenu(item));

  const link = item.querySelector(".category-nav-link");
  if (link) {
    link.addEventListener("click", event => {
      if (window.matchMedia("(max-width: 768px)").matches) {
        return;
      }

      event.preventDefault();
      if (item.classList.contains("menu-open")) {
        closeCategoryMenu(item, 0);
      } else {
        openCategoryMenu(item);
      }
    });
  }
});

if (mobileMenuToggle && mobileCategoryMenu) {
  mobileMenuToggle.addEventListener("click", event => {
    event.stopPropagation();
    const isOpen = mobileCategoryMenu.classList.toggle("open");
    mobileMenuToggle.setAttribute("aria-expanded", String(isOpen));
  });
}

function filterProducts(category) {
  document.querySelectorAll(".filter-btn").forEach(button => {
    button.classList.toggle("active", button.dataset.filter === category);
  });

  const cards = document.querySelectorAll("#allProductsGrid .prod-card");
  let visible = 0;

  cards.forEach(card => {
    const categoryIds = (card.dataset.categoryIds || "")
      .split(",")
      .filter(Boolean);
    const matches = category === "All" || categoryIds.includes(String(category));
    card.classList.toggle("visible", matches);
    if (matches) visible += 1;
  });

  document.getElementById("allProductsCount").textContent =
    `Showing ${visible} piece${visible === 1 ? "" : "s"}`;
}

const revealObserver = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add("visible");
      revealObserver.unobserve(entry.target);
    }
  });
}, { threshold: 0.1 });

function observeReveal() {
  document.querySelectorAll(".reveal:not(.visible)").forEach(element => {
    revealObserver.observe(element);
  });
}

document.addEventListener("click", event => {
  if (!event.target.closest("[data-category-menu]") && !event.target.closest("#mobileCategoryMenu")) {
    closeAllCategoryMenus();
    if (mobileCategoryMenu) mobileCategoryMenu.classList.remove("open");
    if (mobileMenuToggle) mobileMenuToggle.setAttribute("aria-expanded", "false");
  }

  const actionElement = event.target.closest("[data-action]");

  if (actionElement) {
    const id = Number(actionElement.dataset.id);

    if (actionElement.dataset.action === "open-modal" && id) {
      openModal(id);
      return;
    }

    if (actionElement.dataset.action === "add-to-cart" && id) {
      event.stopPropagation();
      addToCart(id);
      return;
    }
  }

  const pageElement = event.target.closest("[data-page]");
  if (pageElement) {
    showPage(pageElement.dataset.page, pageElement.dataset.filter || "All");
    return;
  }

  const filterButton = event.target.closest(".filter-btn[data-filter]");
  if (filterButton) {
    filterProducts(filterButton.dataset.filter);
  }
});

document.getElementById("navLogo").addEventListener("click", () => showPage("home"));
document.getElementById("searchOpenBtn").addEventListener("click", openSearch);
document.getElementById("searchCloseBtn").addEventListener("click", closeSearch);
document.getElementById("searchBackdrop").addEventListener("click", closeSearch);
document.getElementById("modalBackdrop").addEventListener("click", closeModal);
document.getElementById("modalCloseBtn").addEventListener("click", closeModal);

document.querySelectorAll(".search-tag[data-search]").forEach(button => {
  button.addEventListener("click", () => {
    const input = document.getElementById("searchInput");
    input.value = button.dataset.search;
    input.dispatchEvent(new Event("input"));
  });
});

document.addEventListener("keydown", event => {
  if (event.key === "Escape") {
    closeSearch();
    closeModal();
    closeAllCategoryMenus();
    if (mobileCategoryMenu) mobileCategoryMenu.classList.remove("open");
    if (mobileMenuToggle) mobileMenuToggle.setAttribute("aria-expanded", "false");
  }
});

document.getElementById("searchForm").addEventListener("submit", event => {
  const query = document.getElementById("searchInput").value.trim();
  if (!query) event.preventDefault();
});

filterProducts("All");
observeReveal();
updateCartBadge();
