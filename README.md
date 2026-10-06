# Savora — Online Food Ordering System

Professional demo storefront for browsing restaurants, building a cart, checking out, and tracking an order.

## Features

- Home page with featured kitchens and search
- Restaurant directory with cuisine filters
- Per-restaurant menus with photos and INR pricing
- Cart with quantities, delivery fee, and 5% GST
- Checkout form (delivery details + payment method)
- Order confirmation with a tracking timeline
- Cart persisted in the browser (`localStorage`)

## Run locally

Open `index.html` in a browser, or from this folder:

```bash
python -m http.server 8080
```

Then visit [http://localhost:8080](http://localhost:8080).

## Stack

HTML, CSS, and vanilla JavaScript. No build step or backend required — suitable as a front-end project, portfolio piece, or starting point for a full stack.

## Sample data

Six restaurants (Indian, Italian, Japanese, Healthy, American, Mexican) live in `js/data.js`.
