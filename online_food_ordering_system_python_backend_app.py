import os
import sys
import json
import sqlite3
import urllib.request
import urllib.parse
import threading
import time
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime

# ==========================================
# CONFIGURATION & CONSTANTS
# ==========================================
DB_FILE = "food_ordering.db"
DEFAULT_PORT = 8000
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    icon TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dishes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    price REAL NOT NULL,
    rating REAL DEFAULT 5.0,
    prep_time TEXT NOT NULL,
    is_veg INTEGER DEFAULT 0,
    is_popular INTEGER DEFAULT 0,
    badge TEXT DEFAULT 'Popular',
    image_url TEXT NOT NULL,
    description TEXT NOT NULL,
    FOREIGN KEY (category_id) REFERENCES categories (id)
);

CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL,
    status_step INTEGER DEFAULT 1,
    subtotal REAL NOT NULL,
    delivery_fee REAL NOT NULL,
    discount REAL DEFAULT 0.0,
    tax REAL NOT NULL,
    total REAL NOT NULL,
    delivery_address TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    customer_phone TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    dish_id INTEGER NOT NULL,
    dish_name TEXT NOT NULL,
    portion_size TEXT DEFAULT 'Standard',
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    total_price REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders (id)
);
"""

class DatabaseManager:
    """Thread-safe SQLite Database Manager with Context Protocol."""
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executescript(CREATE_TABLES_SQL)
            conn.commit()
        self.seed_if_empty()

    def seed_if_empty(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM categories")
            if cursor.fetchone()["count"] == 0:
                print("🌱 Seeding initial food ordering menu data...")
                
                categories = [
                    ("Burgers", "burgers", "fa-burger"),
                    ("Pizza", "pizza", "fa-pizza-slice"),
                    ("Asian", "asian", "fa-bowl-rice"),
                    ("Healthy", "healthy", "fa-leaf"),
                    ("Italian", "italian", "fa-utensils"),
                    ("Desserts", "desserts", "fa-ice-cream"),
                    ("Drinks", "drinks", "fa-glass-water")
                ]
                cursor.executemany("INSERT INTO categories (name, slug, icon) VALUES (?, ?, ?)", categories)
                
                # Fetch category IDs
                cat_map = {row["name"]: row["id"] for row in cursor.execute("SELECT name, id FROM categories").fetchall()}

                dishes = [
                    ("Truffle Smash Cheeseburger", cat_map["Burgers"], 14.99, 4.9, "20-25 min", 0, 1, "Best Seller", "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=600&q=80", "Double Angus beef patties, aged black truffle aioli, smoked cheddar, brioche bun."),
                    ("Artisanal Margherita Supreme", cat_map["Pizza"], 16.50, 4.8, "25-30 min", 1, 1, "Chef Special", "https://images.unsplash.com/photo-1604382354936-07c5d9983bd3?auto=format&fit=crop&w=600&q=80", "San Marzano tomato base, fresh buffalo mozzarella, hand-picked basil leaves."),
                    ("Tokyo Tonkotsu Ramen", cat_map["Asian"], 15.25, 4.9, "15-20 min", 0, 1, "Top Rated", "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=600&q=80", "Rich 12-hour pork bone broth, tender chashu belly, ajitsuke tamago egg, wheat noodles."),
                    ("Avocado Quinoa Buddha Bowl", cat_map["Healthy"], 13.50, 4.7, "15-20 min", 1, 0, "Healthy Pick", "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=600&q=80", "Organic tri-color quinoa, sliced hass avocado, roasted chickpeas, kale, tahini lemon dressing."),
                    ("Creamy Tuscan Chicken Pasta", cat_map["Italian"], 17.00, 4.8, "20-25 min", 0, 1, "Popular", "https://images.unsplash.com/photo-1621996346565-e3def6164286?auto=format&fit=crop&w=600&q=80", "Penne pasta in garlic parmesan cream sauce, sun-dried tomatoes, baby spinach, seared chicken."),
                    ("Matcha Lava Molten Cake", cat_map["Desserts"], 8.99, 4.9, "10-15 min", 1, 0, "Sweet Tooth", "https://images.unsplash.com/photo-1587314168485-3236d6710814?auto=format&fit=crop&w=600&q=80", "Warm Uji matcha green tea lava cake served with a scoop of Madagascar vanilla gelato."),
                    ("Dragonfruit Mango Smoothie", cat_map["Drinks"], 6.50, 4.6, "5-10 min", 1, 0, "Refreshing", "https://images.unsplash.com/photo-1553530666-ba11a7da3888?auto=format&fit=crop&w=600&q=80", "Blended pink dragonfruit, Alphonso mango, coconut water, mint leaves, and chia seeds.")
                ]
                cursor.executemany("""
                    INSERT INTO dishes (name, category_id, price, rating, prep_time, is_veg, is_popular, badge, image_url, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, dishes)
                conn.commit()

db = DatabaseManager()

class GeminiAIService:
    """Python interface for Google Gemini API standard library request."""
    @staticmethod
    def get_recommendation(prompt: str, menu_summary: List[Dict[str, Any]]) -> str:
        if not GEMINI_API_KEY:
            return (
                f"🤖 [AI Concierge Offline Mode]: Based on your preference for '{prompt}', "
                "we recommend trying our top-rated **Truffle Smash Cheeseburger** paired with a "
                "refreshing **Dragonfruit Mango Smoothie**!"
            )
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={GEMINI_API_KEY}"
        system_prompt = (
            "You are FeastDash's Senior AI Culinary Concierge. "
            f"Current Menu: {json.dumps(menu_summary)}. "
            "Recommend 2 matching dishes with short explanations and a drink pairing. Format neatly with markdown."
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]}
        }
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            return f"Unable to reach Gemini AI API: {str(e)}. Try ordering our Best Seller Truffle Smash Cheeseburger!"

class OrderSimulatorThread(threading.Thread):
    """Background Daemon Thread simulating live order lifecycle steps."""
    def __init__(self, db_manager: DatabaseManager):
        super().__init__(daemon=True)
        self.db_manager = db_manager

    def run(self):
        while True:
            time.sleep(10)
            try:
                with self.db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    orders = cursor.execute("SELECT id, status_step FROM orders WHERE status_step < 4").fetchall()
                    for ord_row in orders:
                        next_step = ord_row["status_step"] + 1
                        status_text = {
                            2: "Kitchen Preparing",
                            3: "Out for Delivery",
                            4: "Delivered"
                        }.get(next_step, "Processing")
                        cursor.execute(
                            "UPDATE orders SET status = ?, status_step = ? WHERE id = ?",
                            (status_text, next_step, ord_row["id"])
                        )
                    conn.commit()
            except Exception as err:
                print(f"Error in OrderSimulatorThread: {err}")

# Start background simulator
OrderSimulatorThread(db).start()

class FoodOrderRequestHandler(BaseHTTPRequestHandler):
    """REST API & Web UI Server Handler."""

    def _set_json_headers(self, status_code: int = 200):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _set_html_headers(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_json_headers(200)

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # Route: Serve Single Page Web Dashboard
        if path == "/" or path == "/index.html":
            self._set_html_headers()
            self.wfile.write(HTML_UI_TEMPLATE.encode('utf-8'))
            return

        # Route: GET /api/categories
        if path == "/api/categories":
            with db.get_connection() as conn:
                rows = conn.cursor().execute("SELECT * FROM categories").fetchall()
                data = [dict(r) for r in rows]
            self._set_json_headers()
            self.wfile.write(json.dumps({"success": True, "data": data}).encode('utf-8'))
            return

        # Route: GET /api/dishes
        if path == "/api/dishes":
            category = query.get("category", ["All"])[0]
            search = query.get("search", [""])[0].lower()
            veg_only = query.get("veg", ["0"])[0] == "1"

            sql = """
                SELECT d.*, c.name as category_name 
                FROM dishes d 
                JOIN categories c ON d.category_id = c.id
                WHERE 1=1
            """
            params = []
            if category != "All":
                sql += " AND c.name = ?"
                params.append(category)
            if veg_only:
                sql += " AND d.is_veg = 1"
            if search:
                sql += " AND (LOWER(d.name) LIKE ? OR LOWER(d.description) LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%"])

            with db.get_connection() as conn:
                rows = conn.cursor().execute(sql, params).fetchall()
                dishes = [dict(r) for r in rows]

            self._set_json_headers()
            self.wfile.write(json.dumps({"success": True, "count": len(dishes), "data": dishes}).encode('utf-8'))
            return

        # Route: GET /api/orders
        if path == "/api/orders":
            with db.get_connection() as conn:
                orders_rows = conn.cursor().execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
                result = []
                for o in orders_rows:
                    ord_dict = dict(o)
                    items_rows = conn.cursor().execute("SELECT * FROM order_items WHERE order_id = ?", (ord_dict["id"],)).fetchall()
                    ord_dict["items"] = [dict(i) for i in items_rows]
                    result.append(ord_dict)

            self._set_json_headers()
            self.wfile.write(json.dumps({"success": True, "data": result}).encode('utf-8'))
            return

        # Route: GET /api/admin/stats
        if path == "/api/admin/stats":
            with db.get_connection() as conn:
                cursor = conn.cursor()
                total_revenue = cursor.execute("SELECT SUM(total) as rev FROM orders").fetchone()["rev"] or 0.0
                total_orders = cursor.execute("SELECT COUNT(*) as cnt FROM orders").fetchone()["cnt"] or 0
                popular_dish = cursor.execute("""
                    SELECT dish_name, SUM(quantity) as qty FROM order_items 
                    GROUP BY dish_name ORDER BY qty DESC LIMIT 1
                """).fetchone()

            stats = {
                "total_revenue": round(total_revenue, 2),
                "total_orders": total_orders,
                "top_seller": popular_dish["dish_name"] if popular_dish else "None"
            }
            self._set_json_headers()
            self.wfile.write(json.dumps({"success": True, "stats": stats}).encode('utf-8'))
            return

        # 404 Fallback
        self._set_json_headers(404)
        self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        payload = json.loads(body.decode('utf-8')) if body else {}

        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        # Route: POST /api/orders
        if path == "/api/orders":
            items = payload.get("items", [])
            address = payload.get("delivery_address", "123 Main Street")
            customer_name = payload.get("customer_name", "Valued Customer")
            customer_phone = payload.get("customer_phone", "+1 555-0192")
            promo_code = payload.get("promo_code", "").upper()

            if not items:
                self._set_json_headers(400)
                self.wfile.write(json.dumps({"error": "Cart items required"}).encode('utf-8'))
                return

            subtotal = sum(i["unit_price"] * i["quantity"] for i in items)
            discount_pct = 0.20 if promo_code in ["FEAST20", "WELCOME50"] else 0.0
            discount = subtotal * discount_pct
            delivery_fee = 2.99
            tax = (subtotal - discount) * 0.08
            total = (subtotal - discount) + delivery_fee + tax

            order_id = f"ORD-{int(time.time())}"

            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO orders (id, status, status_step, subtotal, delivery_fee, discount, tax, total, delivery_address, customer_name, customer_phone)
                    VALUES (?, 'Order Confirmed', 1, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (order_id, subtotal, delivery_fee, discount, tax, total, address, customer_name, customer_phone))

                for item in items:
                    cursor.execute("""
                        INSERT INTO order_items (order_id, dish_id, dish_name, portion_size, quantity, unit_price, total_price)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (order_id, item.get("dish_id", 1), item["dish_name"], item.get("portion_size", "Standard"), item["quantity"], item["unit_price"], item["unit_price"] * item["quantity"]))
                conn.commit()

            self._set_json_headers(201)
            self.wfile.write(json.dumps({
                "success": True,
                "order_id": order_id,
                "total": round(total, 2),
                "message": "Order created successfully! Live tracking active."
            }).encode('utf-8'))
            return

        # Route: POST /api/ai/recommend
        if path == "/api/ai/recommend":
            prompt = payload.get("prompt", "Recommend a nice meal")
            with db.get_connection() as conn:
                dishes_rows = conn.cursor().execute("SELECT name, price, is_veg FROM dishes").fetchall()
                menu_summary = [dict(r) for r in dishes_rows]

            ai_response = GeminiAIService.get_recommendation(prompt, menu_summary)
            self._set_json_headers(200)
            self.wfile.write(json.dumps({"success": True, "recommendation": ai_response}).encode('utf-8'))
            return

        self._set_json_headers(404)
        self.wfile.write(json.dumps({"error": "POST Endpoint not found"}).encode('utf-8'))

HTML_UI_TEMPLATE = """<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FeastDash | Python-Powered Food Ordering System</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Plus Jakarta Sans', sans-serif; }
    </style>
</head>
<body class="bg-slate-900 text-slate-100 min-h-full flex flex-col">

    <!-- Navbar -->
    <header class="sticky top-0 z-50 bg-slate-800/90 backdrop-blur-md border-b border-slate-700 px-6 py-4 flex justify-between items-center">
        <div class="flex items-center gap-3 cursor-pointer" onclick="loadMenu()">
            <div class="w-10 h-10 rounded-xl bg-orange-500 flex items-center justify-center font-black text-xl text-white shadow-lg shadow-orange-500/30">
                <i class="fa-solid fa-utensils"></i>
            </div>
            <div>
                <h1 class="text-xl font-extrabold bg-gradient-to-r from-orange-400 to-amber-400 bg-clip-text text-transparent">FeastDash</h1>
                <span class="text-xs text-emerald-400 font-bold">Python REST Backend Active</span>
            </div>
        </div>

        <div class="flex items-center gap-4">
            <button onclick="toggleTab('menu')" id="nav-menu" class="px-4 py-2 rounded-xl text-xs font-bold bg-orange-500 text-white">Menu</button>
            <button onclick="toggleTab('ai')" id="nav-ai" class="px-4 py-2 rounded-xl text-xs font-bold bg-slate-700 hover:bg-slate-600">AI Concierge</button>
            <button onclick="toggleTab('orders')" id="nav-orders" class="px-4 py-2 rounded-xl text-xs font-bold bg-slate-700 hover:bg-slate-600">Orders</button>
            <button onclick="toggleCartDrawer()" class="relative bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-xl font-bold text-xs flex items-center gap-2">
                <i class="fa-solid fa-bag-shopping"></i> Cart (<span id="cart-count">0</span>)
            </button>
        </div>
    </header>

    <!-- Main Container -->
    <main class="flex-1 max-w-7xl w-full mx-auto p-6">
        
        <!-- SECTION: MENU -->
        <section id="section-menu" class="space-y-6">
            <div class="bg-gradient-to-r from-slate-800 to-slate-900 border border-slate-700 rounded-3xl p-8 flex flex-col md:flex-row justify-between items-center gap-6">
                <div>
                    <span class="px-3 py-1 rounded-full text-xs font-bold bg-orange-500/20 text-orange-400 border border-orange-500/30">Python 3.10+ Standard Library Architecture</span>
                    <h2 class="text-3xl font-black mt-2">Delicious Food, Delivered in 30 Mins</h2>
                    <p class="text-xs text-slate-400 mt-1">Order online from our Python SQLite database backend REST APIs.</p>
                </div>
                <div class="flex gap-2 w-full md:w-auto">
                    <input id="search-input" oninput="loadMenu()" type="text" placeholder="Search dishes..." class="bg-slate-900 border border-slate-700 text-xs text-white px-4 py-3 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-500 w-full md:w-64">
                </div>
            </div>

            <!-- Category Pills -->
            <div id="category-pills" class="flex gap-2 overflow-x-auto pb-2">
                <!-- Injected dynamically -->
            </div>

            <!-- Dishes Grid -->
            <div id="dishes-grid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                <!-- Injected dynamically -->
            </div>
        </section>

        <!-- SECTION: AI CONCIERGE -->
        <section id="section-ai" class="hidden space-y-6">
            <div class="bg-slate-800 border border-purple-800/40 rounded-3xl p-8 space-y-4">
                <span class="px-3 py-1 rounded-full text-xs font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">Gemini AI Python Client</span>
                <h2 class="text-2xl font-black">Ask AI Culinary Concierge</h2>
                <p class="text-xs text-slate-400">Describe your hunger, budget, or mood, and let Gemini curate your meal!</p>
                
                <textarea id="ai-prompt" rows="3" class="w-full bg-slate-900 border border-slate-700 text-xs text-white p-4 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500" placeholder="e.g. I want a spicy high-protein meal with a refreshing cold drink..."></textarea>
                
                <button onclick="askAi()" id="ai-btn" class="bg-purple-600 hover:bg-purple-700 text-white font-bold text-xs px-6 py-3 rounded-xl flex items-center gap-2">
                    <i class="fa-solid fa-wand-magic-sparkles"></i> Get Recommendation
                </button>

                <div id="ai-output" class="hidden bg-slate-900 p-4 rounded-xl border border-slate-700 text-xs text-slate-300 leading-relaxed whitespace-pre-wrap"></div>
            </div>
        </section>

        <!-- SECTION: ORDERS -->
        <section id="section-orders" class="hidden space-y-6">
            <h2 class="text-2xl font-black">Live Order History & Tracker</h2>
            <div id="orders-list" class="space-y-4">
                <!-- Injected dynamically -->
            </div>
        </section>
    </main>

    <!-- Cart Drawer -->
    <div id="cart-drawer" class="fixed inset-y-0 right-0 w-96 bg-slate-800 border-l border-slate-700 p-6 z-50 transform translate-x-full transition-transform duration-300 flex flex-col justify-between shadow-2xl">
        <div class="space-y-4">
            <div class="flex justify-between items-center border-b border-slate-700 pb-3">
                <h3 class="font-extrabold text-base">Your Cart</h3>
                <button onclick="toggleCartDrawer()" class="text-slate-400 hover:text-white"><i class="fa-solid fa-xmark text-lg"></i></button>
            </div>
            <div id="cart-items" class="space-y-3 max-h-96 overflow-y-auto"></div>
        </div>

        <div class="border-t border-slate-700 pt-4 space-y-3">
            <input id="promo-code" type="text" placeholder="Promo code (e.g. FEAST20)" class="w-full bg-slate-900 border border-slate-700 text-xs p-2.5 rounded-xl uppercase">
            <div class="flex justify-between text-xs font-extrabold">
                <span>Subtotal</span>
                <span id="cart-subtotal">$0.00</span>
            </div>
            <button onclick="checkout()" class="w-full bg-orange-500 hover:bg-orange-600 text-white font-bold py-3 rounded-xl text-xs transition-all shadow-lg shadow-orange-500/30">
                Place Order Now
            </button>
        </div>
    </div>

    <script>
        let currentCategory = "All";
        let cart = [];

        document.addEventListener("DOMContentLoaded", () => {
            loadCategories();
            loadMenu();
            loadOrders();
            setInterval(loadOrders, 5000); // Poll live order updates
        });

        function toggleTab(tab) {
            ['menu', 'ai', 'orders'].forEach(t => {
                document.getElementById(`section-${t}`).classList.toggle('hidden', t !== tab);
                const btn = document.getElementById(`nav-${t}`);
                if (t === tab) {
                    btn.className = "px-4 py-2 rounded-xl text-xs font-bold bg-orange-500 text-white";
                } else {
                    btn.className = "px-4 py-2 rounded-xl text-xs font-bold bg-slate-700 hover:bg-slate-600";
                }
            });
        }

        async function loadCategories() {
            const res = await fetch('/api/categories');
            const data = await res.json();
            const container = document.getElementById('category-pills');
            
            let html = `<button onclick="filterCat('All')" class="px-4 py-2 rounded-xl text-xs font-bold ${currentCategory==='All'?'bg-orange-500 text-white':'bg-slate-800 text-slate-300 border border-slate-700'}">All</button>`;
            data.data.forEach(c => {
                html += `<button onclick="filterCat('${c.name}')" class="px-4 py-2 rounded-xl text-xs font-bold ${currentCategory===c.name?'bg-orange-500 text-white':'bg-slate-800 text-slate-300 border border-slate-700'}">${c.name}</button>`;
            });
            container.innerHTML = html;
        }

        function filterCat(cat) {
            currentCategory = cat;
            loadCategories();
            loadMenu();
        }

        async function loadMenu() {
            const search = document.getElementById('search-input').value;
            const res = await fetch(`/api/dishes?category=${currentCategory}&search=${encodeURIComponent(search)}`);
            const data = await res.json();
            const grid = document.getElementById('dishes-grid');

            grid.innerHTML = data.data.map(d => `
                <div class="bg-slate-800 border border-slate-700 rounded-2xl overflow-hidden flex flex-col justify-between hover:border-orange-500/50 transition-all">
                    <div>
                        <img src="${d.image_url}" class="h-40 w-full object-cover">
                        <div class="p-4 space-y-2">
                            <span class="text-[10px] font-bold uppercase text-orange-400 bg-orange-500/10 px-2 py-0.5 rounded-full">${d.badge}</span>
                            <h3 class="font-extrabold text-sm">${d.name}</h3>
                            <p class="text-xs text-slate-400 leading-relaxed line-clamp-2">${d.description}</p>
                        </div>
                    </div>
                    <div class="p-4 border-t border-slate-700/60 flex justify-between items-center">
                        <span class="font-black text-sm">$${d.price.toFixed(2)}</span>
                        <button onclick="addToCart('${d.id}', '${d.name}', ${d.price})" class="bg-orange-500/20 hover:bg-orange-500 text-orange-400 hover:text-white font-bold text-xs px-3 py-1.5 rounded-lg transition-all">
                            + Add
                        </button>
                    </div>
                </div>
            `).join('');
        }

        function addToCart(id, name, price) {
            const existing = cart.find(i => i.dish_id === id);
            if (existing) {
                existing.quantity++;
            } else {
                cart.push({ dish_id: id, dish_name: name, unit_price: price, quantity: 1 });
            }
            renderCart();
        }

        function renderCart() {
            document.getElementById('cart-count').innerText = cart.reduce((s, i) => s + i.quantity, 0);
            const container = document.getElementById('cart-items');
            
            let sub = 0;
            container.innerHTML = cart.map(i => {
                sub += i.unit_price * i.quantity;
                return `
                    <div class="flex justify-between items-center bg-slate-900 p-3 rounded-xl text-xs">
                        <div>
                            <div class="font-bold">${i.dish_name}</div>
                            <div class="text-slate-400">$${i.unit_price.toFixed(2)} x ${i.quantity}</div>
                        </div>
                        <span class="font-black text-orange-400">$${(i.unit_price * i.quantity).toFixed(2)}</span>
                    </div>
                `;
            }).join('');

            document.getElementById('cart-subtotal').innerText = `$${sub.toFixed(2)}`;
        }

        function toggleCartDrawer() {
            document.getElementById('cart-drawer').classList.toggle('translate-x-full');
        }

        async function checkout() {
            if (cart.length === 0) return alert("Cart is empty!");
            const promo = document.getElementById('promo-code').value;
            
            const res = await fetch('/api/orders', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    items: cart,
                    delivery_address: "742 Evergreen Terrace",
                    promo_code: promo
                })
            });

            const data = await res.json();
            if (data.success) {
                cart = [];
                renderCart();
                toggleCartDrawer();
                toggleTab('orders');
                loadOrders();
            }
        }

        async function loadOrders() {
            const res = await fetch('/api/orders');
            const data = await res.json();
            const container = document.getElementById('orders-list');

            if (data.data.length === 0) {
                container.innerHTML = `<div class="text-slate-500 text-xs">No active orders found.</div>`;
                return;
            }

            container.innerHTML = data.data.map(o => `
                <div class="bg-slate-800 border border-slate-700 p-5 rounded-2xl space-y-3">
                    <div class="flex justify-between items-center">
                        <div>
                            <span class="text-xs font-bold text-orange-400">${o.id}</span>
                            <h4 class="font-black text-base">Status: ${o.status}</h4>
                        </div>
                        <span class="font-black text-sm text-emerald-400">$${o.total.toFixed(2)}</span>
                    </div>
                    <div class="w-full bg-slate-900 rounded-full h-2 overflow-hidden">
                        <div class="bg-gradient-to-r from-orange-500 to-amber-500 h-full transition-all duration-500" style="width: ${(o.status_step/4)*100}%"></div>
                    </div>
                </div>
            `).join('');
        }

        async function askAi() {
            const prompt = document.getElementById('ai-prompt').value;
            const btn = document.getElementById('ai-btn');
            const out = document.getElementById('ai-output');

            if (!prompt) return;
            btn.disabled = true;
            out.classList.remove('hidden');
            out.innerText = "Analyzing menu and consulting Gemini AI model...";

            const res = await fetch('/api/ai/recommend', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt })
            });
            const data = await res.json();
            out.innerText = data.recommendation;
            btn.disabled = false;
        }
    </script>
</body>
</html>
"""

def main():
    parser = argparse.ArgumentParser(description="FeastDash Online Food Ordering System - Python Backend")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to run the HTTP REST server on")
    parser.add_argument("--seed-only", action="store_true", help="Seed the SQLite database and exit")
    parser.add_argument("--stats", action="store_true", help="Print backend sales metrics and exit")
    args = parser.parse_args()

    if args.seed_only:
        db.seed_if_empty()
        print("✅ Database seeding complete.")
        sys.exit(0)

    if args.stats:
        with db.get_connection() as conn:
            cnt = conn.cursor().execute("SELECT COUNT(*) as c FROM orders").fetchone()["c"]
            rev = conn.cursor().execute("SELECT SUM(total) as r FROM orders").fetchone()["r"] or 0.0
            print(f"📊 FeastDash System Metrics:\n Total Orders: {cnt}\n Total Revenue: ${rev:.2f}")
        sys.exit(0)

    server_address = ('', args.port)
    httpd = HTTPServer(server_address, FoodOrderRequestHandler)
    print(f"🚀 FeastDash Food Ordering System Python Server Running on http://localhost:{args.port}")
    print(f"🔗 Access Web UI: http://localhost:{args.port}/")
    print(f"📡 REST API Base: http://localhost:{args.port}/api/dishes")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n Shutting down FeastDash Python Server gracefully.")
        httpd.server_close()

if __name__ == "__main__":
    main()