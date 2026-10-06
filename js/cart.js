const CART_KEY = "savora-cart";
const ORDER_KEY = "savora-last-order";

const Cart = {
  read() {
    try {
      return JSON.parse(localStorage.getItem(CART_KEY)) || [];
    } catch {
      return [];
    }
  },
  write(items) {
    localStorage.setItem(CART_KEY, JSON.stringify(items));
    Cart.updateBadges();
  },
  add(item, restaurant) {
    const items = Cart.read();
    if (items.length && items[0].restaurantId !== restaurant.id) {
      if (!confirm(`Your cart has items from ${items[0].restaurantName}. Replace with ${restaurant.name}?`)) {
        return false;
      }
      items.length = 0;
    }
    const existing = items.find((row) => row.id === item.id);
    if (existing) existing.qty += 1;
    else {
      items.push({
        id: item.id,
        name: item.name,
        price: item.price,
        qty: 1,
        restaurantId: restaurant.id,
        restaurantName: restaurant.name,
        fee: restaurant.fee
      });
    }
    Cart.write(items);
    Savora.toast(`${item.name} added to cart`);
    return true;
  },
  setQty(id, qty) {
    let items = Cart.read();
    if (qty <= 0) items = items.filter((row) => row.id !== id);
    else items = items.map((row) => (row.id === id ? { ...row, qty } : row));
    Cart.write(items);
  },
  clear() {
    Cart.write([]);
  },
  totals() {
    const items = Cart.read();
    const subtotal = items.reduce((sum, row) => sum + row.price * row.qty, 0);
    const fee = items.length ? items[0].fee : 0;
    const tax = Math.round(subtotal * 0.05);
    return { items, subtotal, fee, tax, total: subtotal + fee + tax };
  },
  updateBadges() {
    const count = Cart.read().reduce((sum, row) => sum + row.qty, 0);
    document.querySelectorAll("[data-cart-count]").forEach((el) => {
      el.textContent = String(count);
      el.hidden = count === 0;
    });
  }
};

const Savora = {
  restaurants: () => window.SAVORA_DATA.restaurants,
  byId: (id) => window.SAVORA_DATA.restaurants.find((r) => r.id === id),
  inr: (n) => `₹${n.toLocaleString("en-IN")}`,
  toast(message) {
    let el = document.querySelector(".toast");
    if (!el) {
      el = document.createElement("div");
      el.className = "toast";
      document.body.appendChild(el);
    }
    el.textContent = message;
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), 1800);
  },
  param(name) {
    return new URLSearchParams(location.search).get(name);
  }
};

document.addEventListener("DOMContentLoaded", Cart.updateBadges);
