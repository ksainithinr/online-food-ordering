function restaurantCard(r) {
  return `
    <a class="card" href="menu.html?id=${r.id}">
      <img src="${r.image}" alt="${r.name}">
      <div class="card-body">
        <span class="badge">${r.cuisine}</span>
        <h3>${r.name}</h3>
        <div class="meta">
          <span class="star">★ ${r.rating}</span>
          <span>${r.eta}</span>
          <span>Delivery ${Savora.inr(r.fee)}</span>
        </div>
      </div>
    </a>`;
}

function renderHome() {
  const featured = document.querySelector("[data-featured]");
  if (!featured) return;
  featured.innerHTML = Savora.restaurants().slice(0, 6).map(restaurantCard).join("");
}

function renderRestaurants() {
  const grid = document.querySelector("[data-restaurants]");
  const filters = document.querySelector("[data-filters]");
  if (!grid) return;
  const cuisines = ["All", ...new Set(Savora.restaurants().map((r) => r.cuisine))];
  let active = "All";
  const q = (Savora.param("q") || "").toLowerCase();
  const search = document.querySelector("[data-search]");
  if (search && q) search.value = Savora.param("q");

  const paint = () => {
    const query = (search?.value || q || "").toLowerCase();
    grid.innerHTML = Savora.restaurants()
      .filter((r) => active === "All" || r.cuisine === active)
      .filter((r) => !query || `${r.name} ${r.cuisine} ${r.blurb}`.toLowerCase().includes(query))
      .map(restaurantCard)
      .join("") || `<p class="empty">No kitchens match that search.</p>`;
  };

  filters.innerHTML = cuisines
    .map((c, i) => `<button class="chip ${i === 0 ? "active" : ""}" data-cuisine="${c}">${c}</button>`)
    .join("");
  filters.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-cuisine]");
    if (!btn) return;
    active = btn.dataset.cuisine;
    filters.querySelectorAll(".chip").forEach((el) => el.classList.toggle("active", el === btn));
    paint();
  });
  search?.addEventListener("input", paint);
  paint();
}

function renderMenu() {
  const restaurant = Savora.byId(Savora.param("id"));
  if (!restaurant) return;
  document.querySelector("[data-rest-name]").textContent = restaurant.name;
  document.querySelector("[data-rest-meta]").innerHTML = `
    <span class="badge">${restaurant.cuisine}</span>
    <span class="star">★ ${restaurant.rating}</span>
    <span>${restaurant.eta}</span>`;
  document.querySelector("[data-hero-img]").src = restaurant.image;
  document.querySelector("[data-blurb]").textContent = restaurant.blurb;
  const list = document.querySelector("[data-menu]");
  list.innerHTML = restaurant.menu
    .map(
      (item) => `
      <article class="menu-item">
        <img src="${item.image}" alt="${item.name}">
        <div>
          <h3>${item.name}</h3>
          <p class="lede" style="margin:6px 0 0">${item.desc}</p>
          <p class="price">${Savora.inr(item.price)}</p>
        </div>
        <button class="btn btn-primary" data-add="${item.id}">Add</button>
      </article>`
    )
    .join("");
  list.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-add]");
    if (!btn) return;
    const item = restaurant.menu.find((m) => m.id === btn.dataset.add);
    Cart.add(item, restaurant);
    renderCartPanel();
  });
  renderCartPanel();
}

function renderCartPanel() {
  const panel = document.querySelector("[data-cart-panel]");
  if (!panel) return;
  const { items, subtotal, fee, tax, total } = Cart.totals();
  if (!items.length) {
    panel.innerHTML = `<h3>Your order</h3><p class="empty">Your cart is empty. Add a dish to get started.</p>`;
    return;
  }
  panel.innerHTML = `
    <h3>${items[0].restaurantName}</h3>
    ${items
      .map(
        (row) => `
      <div class="cart-row">
        <div>
          <strong>${row.name}</strong>
          <div class="qty">
            <button data-qty="${row.id}" data-delta="-1">−</button>
            <span>${row.qty}</span>
            <button data-qty="${row.id}" data-delta="1">+</button>
          </div>
        </div>
        <span>${Savora.inr(row.price * row.qty)}</span>
      </div>`
      )
      .join("")}
    <div class="cart-row"><span>Subtotal</span><span>${Savora.inr(subtotal)}</span></div>
    <div class="cart-row"><span>Delivery</span><span>${Savora.inr(fee)}</span></div>
    <div class="cart-row"><span>GST (5%)</span><span>${Savora.inr(tax)}</span></div>
    <div class="total"><span>Total</span><span>${Savora.inr(total)}</span></div>
    <a class="btn btn-primary btn-full" style="margin-top:16px" href="checkout.html">Checkout</a>`;
  panel.onclick = (e) => {
    const btn = e.target.closest("[data-qty]");
    if (!btn) return;
    const row = Cart.read().find((r) => r.id === btn.dataset.qty);
    Cart.setQty(row.id, row.qty + Number(btn.dataset.delta));
    renderCartPanel();
    if (typeof renderCartPage === "function") renderCartPage();
  };
}

function renderCartPage() {
  const wrap = document.querySelector("[data-cart-page]");
  if (!wrap) return;
  renderCartPanel = renderCartPanel;
  const { items, subtotal, fee, tax, total } = Cart.totals();
  if (!items.length) {
    wrap.innerHTML = `<p class="empty">Your cart is empty.</p><a class="btn btn-primary" href="restaurants.html">Browse restaurants</a>`;
    return;
  }
  wrap.innerHTML = `
    <div class="checkout-grid">
      <div>
        ${items
          .map(
            (row) => `
          <article class="menu-item">
            <div>
              <h3>${row.name}</h3>
              <p>${row.restaurantName}</p>
              <div class="qty">
                <button data-qty="${row.id}" data-delta="-1">−</button>
                <span>${row.qty}</span>
                <button data-qty="${row.id}" data-delta="1">+</button>
              </div>
            </div>
            <strong>${Savora.inr(row.price * row.qty)}</strong>
          </article>`
          )
          .join("")}
      </div>
      <aside class="cart-panel">
        <div class="cart-row"><span>Subtotal</span><span>${Savora.inr(subtotal)}</span></div>
        <div class="cart-row"><span>Delivery</span><span>${Savora.inr(fee)}</span></div>
        <div class="cart-row"><span>GST (5%)</span><span>${Savora.inr(tax)}</span></div>
        <div class="total"><span>Total</span><span>${Savora.inr(total)}</span></div>
        <a class="btn btn-primary btn-full" style="margin-top:16px" href="checkout.html">Proceed to checkout</a>
      </aside>
    </div>`;
  wrap.onclick = (e) => {
    const btn = e.target.closest("[data-qty]");
    if (!btn) return;
    const row = Cart.read().find((r) => r.id === btn.dataset.qty);
    Cart.setQty(row.id, row.qty + Number(btn.dataset.delta));
    renderCartPage();
  };
}

function renderCheckout() {
  const form = document.querySelector("[data-checkout]");
  const summary = document.querySelector("[data-summary]");
  if (!form) return;
  const { items, subtotal, fee, tax, total } = Cart.totals();
  if (!items.length) {
    location.href = "cart.html";
    return;
  }
  summary.innerHTML = `
    <h3>${items[0].restaurantName}</h3>
    ${items.map((row) => `<div class="cart-row"><span>${row.qty} × ${row.name}</span><span>${Savora.inr(row.price * row.qty)}</span></div>`).join("")}
    <div class="total"><span>Pay</span><span>${Savora.inr(total)}</span></div>`;
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    const order = {
      id: "SV-" + Math.random().toString(36).slice(2, 8).toUpperCase(),
      ...data,
      items,
      subtotal,
      fee,
      tax,
      total,
      placedAt: new Date().toISOString()
    };
    localStorage.setItem(ORDER_KEY, JSON.stringify(order));
    Cart.clear();
    location.href = "order.html";
  });
}

function renderOrder() {
  const wrap = document.querySelector("[data-order]");
  if (!wrap) return;
  const order = JSON.parse(localStorage.getItem(ORDER_KEY) || "null");
  if (!order) {
    wrap.innerHTML = `<p class="empty">No recent order found.</p>`;
    return;
  }
  wrap.innerHTML = `
    <p class="kicker">Order confirmed</p>
    <h1>We’re preparing ${order.items[0].restaurantName}</h1>
    <p class="lede">Order <strong>${order.id}</strong> is heading to ${order.address}. Estimated arrival 30–40 minutes.</p>
    <div class="tracker">
      <div class="step done"><strong>Placed</strong><p>Payment received</p></div>
      <div class="step done"><strong>Kitchen</strong><p>Chef started cooking</p></div>
      <div class="step"><strong>On the way</strong><p>Rider assigned soon</p></div>
      <div class="step"><strong>Delivered</strong><p>Enjoy your meal</p></div>
    </div>
    <p class="price">Paid ${Savora.inr(order.total)} · ${order.payment}</p>
    <a class="btn btn-primary" href="index.html">Back home</a>`;
}

document.addEventListener("DOMContentLoaded", () => {
  renderHome();
  renderRestaurants();
  renderMenu();
  renderCartPage();
  renderCheckout();
  renderOrder();
});
