"""
Shopify CRO Checker  v1.0
-------------------------
Paste a Shopify store or product link. The app checks the homepage and a product page,
explains every issue in plain language, shows a simple before/after sketch, and gives
step-by-step fixes (with code and a ready-made AI prompt).

Evidence comes from a Sources library you can edit (add/remove websites, PDFs, documents).

Setup (one time, in a terminal):  pip install requests beautifulsoup4
Run: double-click this file.
"""

import json
import os
import re
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import urlparse, urljoin

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont

import requests
from bs4 import BeautifulSoup

APP_NAME = "Shopify CRO Checker"
CONTACT_EMAIL = "alperhasankizik@gmail.com"   # change this to update the Contact us address
HEADERS = {"User-Agent": "Mozilla/5.0 (Shopify CRO Checker - personal learning project)"}
DATA_DIR = Path.home() / ".shopify_cro_checker"
SOURCES_FILE = DATA_DIR / "sources.json"

# ---------------------------------------------------------------- colours / fonts
C = {
    "navy": "#0A0A0A", "navy2": "#262626", "bg": "#FAFAFA", "card": "#FFFFFF",
    "line": "#E5E5E5", "text": "#0A0A0A", "muted": "#737373", "accent": "#0A0A0A",
    "accent_dark": "#333333", "ok": "#737373", "ok_bg": "#F5F5F5", "bad": "#0A0A0A",
    "bad_bg": "#EDEDED", "hl": "#0A0A0A", "hl_bg": "#FFFFFF",
}
FONT = "Segoe UI" if sys.platform.startswith("win") else "Helvetica"
MARK = "#DC2626"   # the only colour: a pen-style circle around what should change


# ================================================================ SOURCES (evidence library)

DEFAULT_SOURCES = [
    {"id": "baymard", "title": "Baymard Institute – Reasons for checkout abandonment",
     "type": "Website", "location": "https://baymard.com/blog/reduce-cart-abandonment",
     "finding": "Unexpected extra costs are the top reason shoppers abandon checkout (39%), "
                "followed by slow delivery (21%), forced account creation (19%) and a too "
                "complicated checkout (18%).",
     "checks": ["shipping_info", "returns_info", "express_checkout", "free_ship_bar",
                "data_cart_abandon", "data_checkout_drop"]},
    {"id": "spiegel", "title": "Spiegel Research Center – How online reviews influence sales",
     "type": "PDF", "location": "https://www.xait.com/hubfs/Spiegel_Online-Review_eBook_Jun2017_FINAL.pdf",
     "finding": "A product with 5 reviews is about 270% more likely to be bought than one with "
                "none. Purchase likelihood peaks around 4.2–4.7 stars and drops near 5.0. "
                "Verified-buyer reviews raise purchase likelihood by 15%.",
     "checks": ["reviews_present", "review_volume", "rating_credible", "reviews_position"]},
    {"id": "deloitte", "title": "Deloitte / Google – Milliseconds Make Millions",
     "type": "Website", "location": "https://web.dev/case-studies/milliseconds-make-millions",
     "finding": "A 0.1 second faster mobile site raised retail conversion by 8.4% and spend by 9.2%.",
     "checks": ["speed", "page_weight", "data_mobile_gap"]},
    {"id": "shopify_checkout", "title": "Shopify – Shopify Checkout and Shop Pay",
     "type": "Website", "location": "https://www.shopify.com/enterprise/blog/shopify-checkout",
     "finding": "Shopify's own study says Shop Pay can lift conversion by up to 50% vs. guest "
                "checkout (vendor claim, not independent).",
     "checks": ["express_checkout"]},
    {"id": "cb_trust", "title": "craftberry blog – Homepage trust signals test",
     "type": "Website", "location": "https://craftberry.co/",
     "finding": "Moving the Trustpilot rating and service promises above the fold on the "
                "homepage lifted revenue per visitor +35.4% and average order value +26.5%.",
     "checks": ["trust_signals", "home_trust", "shipping_info"]},
    {"id": "cb_video", "title": "craftberry blog – Customer video test",
     "type": "Website", "location": "https://craftberry.co/",
     "finding": "Replacing YouTube channel videos with short clips filmed by customers lifted "
                "revenue per visitor +19.5% and conversion +13.7%.",
     "checks": ["video_ugc"]},
    {"id": "cb_cards", "title": "craftberry blog – Product card savings test",
     "type": "Website", "location": "https://craftberry.co/",
     "finding": "Product cards showing the % saving, compatibility and rating lifted revenue per "
                "visitor +28.2% and conversion +20.6%.",
     "checks": ["sale_savings"]},
    {"id": "cb_shelly", "title": "craftberry case – Shelly",
     "type": "Website", "location": "https://craftberry.co/case-studies/shelly",
     "finding": "'Most Popular' and 'Best Value' badges on multi-packs, with prices unchanged, "
                "lifted conversion +11% and RPV +8%.",
     "checks": ["variant_labels"]},
    {"id": "cb_moonnude", "title": "craftberry case – Moon Nude",
     "type": "Website", "location": "https://craftberry.co/case-studies/moon-nude",
     "finding": "More visible star rating on bestsellers: conversion +14.3%, RPV +23.4%. Bundles "
                "on product pages: RPV +14.7%. Bundles on the homepage: RPV +17.1%.",
     "checks": ["reviews_present", "bundles", "home_bundles"]},
    {"id": "cb_miamante", "title": "craftberry case – Mi Amante",
     "type": "Website", "location": "https://craftberry.co/case-studies/mi-amante",
     "finding": "Reworked product-page upsell: RPV +13.8%. Colour swatches on collection pages: "
                "RPV +7.3%. Rebuilt mobile menu (95.6% of sessions were mobile): RPV +5.5%.",
     "checks": ["upsell", "swatches", "viewport", "data_mobile_gap"]},
    {"id": "cb_enhance", "title": "craftberry case – Enhance",
     "type": "Website", "location": "https://craftberry.co/case-studies/enhance",
     "finding": "Moving reviews from the bottom of the page to just below the hero lifted "
                "conversion +21.0% and RPV +21.6% in 4 weeks.",
     "checks": ["reviews_position"]},
    {"id": "cb_orpheus", "title": "craftberry case – Orpheus",
     "type": "Website", "location": "https://craftberry.co/case-studies/orpheus",
     "finding": "Rebuild with product pages organised around customer questions, reviews and "
                "video near add-to-cart, and a free shipping bar in the cart: conversion +6%.",
     "checks": ["description", "free_ship_bar", "video_ugc"]},
    {"id": "cb_proenergetic", "title": "craftberry case – ProEnergetic",
     "type": "Website", "location": "https://craftberry.co/case-studies/supplement-shopify-brand-proenergetic",
     "finding": "43% faster page load after migration and rebuild.",
     "checks": ["speed", "page_weight"]},
]


def load_sources():
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if SOURCES_FILE.exists():
            saved = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
            # keep built-in sources up to date with checks added in newer versions
            defaults = {d["id"]: d for d in DEFAULT_SOURCES}
            changed = False
            for src in saved:
                d = defaults.get(src.get("id"))
                if d:
                    missing = [c for c in d["checks"] if c not in src.get("checks", [])]
                    if missing:
                        src.setdefault("checks", []).extend(missing)
                        changed = True
            if changed:
                save_sources(saved)
            return saved
    except Exception:
        pass
    save_sources(DEFAULT_SOURCES)
    return [dict(s) for s in DEFAULT_SOURCES]


def save_sources(sources):
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SOURCES_FILE.write_text(json.dumps(sources, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        messagebox.showerror(APP_NAME, f"Could not save sources:\n{e}")


# ================================================================ CHECK LIBRARY
# zone = where on the page the fix goes (used for the visual sketch)
# mode = "add" (element missing) or "move" (element exists but too low)

CHECKS = {
    "add_to_cart": {
        "title": "Add-to-cart button", "zone": "atc", "mode": "add",
        "why": "If shoppers can't find a clear add-to-cart button, nothing else matters. "
               "It is the most important element on the product page.",
        "change": "a clear, standard add-to-cart button", "action": "add the product to cart",
        "metric": "add-to-cart rate",
        "fix": ["Open Shopify admin → Online Store → Themes → Customize.",
                "Open a product page template and select the Product information section.",
                "Make sure the 'Buy buttons' block is present and visible.",
                "If a custom theme hides it, ask the theme developer to restore the standard "
                "product form (form action '/cart/add')."],
        "code": None},
    "atc_above_fold": {
        "title": "Add to cart on the first screen", "zone": "atc", "mode": "move",
        "why": "On a phone, the first screen is all many visitors see before deciding. If the "
               "add-to-cart button is below it, buying takes extra effort and some people leave.",
        "change": "bringing the add-to-cart button onto the first screen on mobile (smaller "
                  "images, shorter text above it, or a sticky add-to-cart bar)",
        "action": "add to cart without scrolling", "metric": "mobile add-to-cart rate",
        "fix": ["Open the product page on your phone and note what sits above the button.",
                "In the theme editor, reduce the image height on mobile or move long text "
                "(descriptions, badges) below the buy buttons.",
                "Or add a sticky add-to-cart bar (many themes have it built in; otherwise a free "
                "app from the Shopify App Store).",
                "Re-run the browser audit and check the button is above the dashed line."],
        "code": None},
    "reviews_present": {
        "title": "Product reviews", "zone": "reviews_top", "mode": "add",
        "why": "Most shoppers look for other people's opinions before buying. Without reviews, "
               "the product feels risky, especially for higher-priced items.",
        "change": "showing the star rating and review count near the product title",
        "action": "trust the product sooner", "metric": "revenue per visitor",
        "fix": ["Install a review app from the Shopify App Store (for example Judge.me, which has "
                "a free plan).",
                "In the theme editor, add the app's 'star rating' block under the product title.",
                "Add the app's 'reviews widget' block on the product page.",
                "Turn on the app's automatic review-request email after delivery."],
        "code": None},
    "reviews_position": {
        "title": "Reviews close to the buy decision", "zone": "reviews_top", "mode": "move",
        "why": "Reviews only help if people see them. Many visitors never scroll to the bottom, "
               "so reviews placed there are invisible to them.",
        "change": "moving reviews (or at least the star rating) directly below the product hero",
        "action": "see social proof before deciding", "metric": "conversion rate",
        "fix": ["Open the theme editor on a product page.",
                "Drag the reviews section up so it sits right below the product information.",
                "Add the star-rating block under the product title as well.",
                "Check the result on mobile, where scrolling is longer."],
        "code": None},
    "review_volume": {
        "title": "Number of reviews", "zone": "reviews_top", "mode": "add",
        "why": "A handful of reviews is not convincing. Research shows the first five reviews "
               "make the biggest difference to buying.",
        "change": "a post-purchase email asking verified buyers to leave a review",
        "action": "trust the product", "metric": "conversion rate",
        "fix": ["In your review app, enable automatic review-request emails.",
                "Send the request a few days after delivery, not right after purchase.",
                "Offer a small incentive (e.g. a discount on the next order) if your app and "
                "local rules allow it.",
                "Import older reviews from other channels if you have them."],
        "code": None},
    "rating_credible": {
        "title": "Rating looks believable", "zone": "reviews_top", "mode": "add",
        "why": "A perfect or near-perfect rating can look fake. Shoppers trust a high rating more "
               "when they can also see a few honest, critical reviews.",
        "change": "showing verified-buyer badges and not hiding critical reviews",
        "action": "trust the rating", "metric": "conversion rate",
        "fix": ["In your review app, show the 'Verified buyer' badge.",
                "Do not filter out 3-star or lower reviews; reply to them politely instead.",
                "Sort reviews by 'most recent' or 'most helpful' rather than 'highest rating'."],
        "code": None},
    "shipping_info": {
        "title": "Shipping information", "zone": "shipping", "mode": "add",
        "why": "Unexpected costs at checkout are the number one reason people abandon their cart. "
               "Telling them the delivery time and cost early removes the surprise.",
        "change": "adding delivery time and cost near the add-to-cart button",
        "action": "avoid surprises at checkout", "metric": "checkout completion rate",
        "fix": ["Open the theme editor on a product page.",
                "Under the buy buttons, add a 'Collapsible row' or 'Text' block.",
                "Title it 'Shipping' and write delivery time and cost in one or two lines.",
                "Link to your full shipping policy (Settings → Policies)."],
        "code": "<!-- Simple shipping line under the buy button -->\n"
                "<p class=\"shipping-note\">🚚 Ships in 1–2 business days · Free shipping over €50</p>\n"
                "<style>.shipping-note{font-size:14px;color:#334155;margin-top:8px}</style>"},
    "returns_info": {
        "title": "Returns information", "zone": "shipping", "mode": "add",
        "why": "People buy more easily when they know they can send the product back. A short "
               "returns promise lowers the risk of buying.",
        "change": "a short returns promise near the add-to-cart button",
        "action": "buy with less risk", "metric": "conversion rate",
        "fix": ["Add a 'Collapsible row' block titled 'Returns' under the buy buttons.",
                "Write the promise in one line, for example '30-day free returns'.",
                "Link to the full refund policy (Settings → Policies)."],
        "code": "<p class=\"returns-note\">↩️ 30-day returns, no questions asked</p>"},
    "trust_signals": {
        "title": "Trust signals near the price", "zone": "trust", "mode": "add",
        "why": "Short promises like free shipping, a guarantee or secure checkout answer doubts "
               "before the shopper has to ask.",
        "change": "showing the store's key promises right below the add-to-cart button",
        "action": "feel confident buying", "metric": "revenue per visitor",
        "fix": ["Pick your three strongest promises (e.g. free shipping, 30-day returns, "
                "2-year warranty).",
                "In the theme editor, add an 'Icon with text' block under the buy buttons.",
                "Use short text, one line each."],
        "code": "<ul class=\"trust-row\">\n  <li>🚚 Free shipping over €50</li>\n"
                "  <li>↩️ 30-day returns</li>\n  <li>🔒 Secure checkout</li>\n</ul>\n"
                "<style>.trust-row{display:flex;gap:16px;list-style:none;padding:0;font-size:14px}</style>"},
    "free_ship_bar": {
        "title": "Free shipping threshold message", "zone": "trust", "mode": "add",
        "why": "Telling shoppers how much more they need to spend for free shipping encourages "
               "them to add one more item, and removes the shipping-cost surprise.",
        "change": "a free shipping progress message in the cart and on product pages",
        "action": "add one more item to their order", "metric": "average order value",
        "fix": ["Decide your free shipping threshold (e.g. €50) in Settings → Shipping and delivery.",
                "Add the code below to your cart drawer or cart page "
                "(Online Store → Themes → Edit code → cart template or cart drawer snippet).",
                "Change 5000 to your threshold in cents (5000 = €50.00).",
                "Preview on mobile and test with an item under and over the threshold."],
        "code": "{% assign threshold = 5000 %}\n"
                "{% assign remaining = threshold | minus: cart.total_price %}\n"
                "{% if remaining > 0 %}\n"
                "  <p class=\"ship-bar\">You're {{ remaining | money }} away from free shipping</p>\n"
                "{% else %}\n"
                "  <p class=\"ship-bar\">🎉 You've unlocked free shipping</p>\n"
                "{% endif %}"},
    "bundles": {
        "title": "Bundles or sets", "zone": "bundles", "mode": "add",
        "why": "A bundle gives shoppers a simple reason to buy more in one order, and it often "
               "feels like better value.",
        "change": "showing a relevant bundle directly on the product page",
        "action": "buy more in one order", "metric": "revenue per visitor",
        "fix": ["Install Shopify's free 'Shopify Bundles' app.",
                "Create a bundle from products that are often bought together.",
                "Show the bundle on the product page with the app's block, near the buy buttons.",
                "Start with one bundle and measure before adding more."],
        "code": None},
    "upsell": {
        "title": "Related products / upsell", "zone": "recs", "mode": "add",
        "why": "Showing products that go well with this one helps shoppers find a second item "
               "and increases order value.",
        "change": "a simple block with complementary products",
        "action": "discover a second product", "metric": "revenue per visitor",
        "fix": ["Install Shopify's free 'Search & Discovery' app.",
                "Set 'Complementary products' for your best sellers.",
                "In the theme editor, add the 'Related products' / 'Complementary products' block "
                "to the product page."],
        "code": None},
    "video_ugc": {
        "title": "Video or customer content", "zone": "hero", "mode": "add",
        "why": "Seeing real people use the product answers questions that photos can't, and it "
               "builds trust.",
        "change": "short videos of real customers using the product, near the product images",
        "action": "see the product in real use", "metric": "revenue per visitor",
        "fix": ["Collect short phone videos from customers (ask in the review email).",
                "In Shopify admin → Products, upload the video to the product's media.",
                "Keep it under 30 seconds and show the product in use in the first seconds."],
        "code": None},
    "page_weight": {
        "title": "Page weight (scripts)", "zone": "page", "mode": "add",
        "why": "Every app adds code that the page must load. Too many scripts slow the page down, "
               "and slow pages lose buyers, especially on mobile.",
        "change": "removing unused app scripts and lightening the theme",
        "action": "reach the product faster", "metric": "conversion rate",
        "fix": ["List your installed apps and uninstall the ones you don't use.",
                "In Edit code, search the theme for leftover code from removed apps.",
                "Compress large images before uploading.",
                "Re-run the speed test after each change."],
        "code": None},
    "speed": {
        "title": "Mobile speed score", "zone": "page", "mode": "add",
        "why": "Even small delays cost sales. Shoppers on phones leave if a page feels slow.",
        "change": "removing unused apps, compressing images and simplifying the theme",
        "action": "reach the product faster on mobile", "metric": "mobile conversion rate",
        "fix": ["Run the page in Google PageSpeed Insights and read the 'Opportunities' list.",
                "Start with the biggest items: large images and unused JavaScript.",
                "Remove apps you don't use; each app adds load time.",
                "Re-test after every change."],
        "code": None},
    "express_checkout": {
        "title": "Express checkout (Shop Pay)", "zone": "atc", "mode": "add",
        "why": "Express checkout lets returning shoppers pay in one or two taps instead of "
               "filling in long forms.",
        "change": "enabling Shop Pay and dynamic checkout buttons",
        "action": "pay in fewer steps", "metric": "checkout completion rate",
        "fix": ["Shopify admin → Settings → Payments: activate Shopify Payments and Shop Pay "
                "(where available in your country).",
                "Theme editor → product page → Buy buttons block → tick 'Show dynamic checkout "
                "buttons'.",
                "Test a purchase on mobile."],
        "code": None},
    "viewport": {
        "title": "Mobile-friendly layout", "zone": "page", "mode": "add",
        "why": "Most e-commerce visits come from phones. A page that doesn't fit the screen is "
               "hard to use and loses buyers.",
        "change": "a responsive mobile layout", "action": "browse and buy on mobile",
        "metric": "mobile conversion rate",
        "fix": ["Edit code → layout/theme.liquid.",
                "Inside <head>, make sure the viewport line below exists.",
                "If the theme is very old, consider a modern free theme such as Dawn."],
        "code": "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"},
    "images": {
        "title": "Number of product images", "zone": "hero", "mode": "add",
        "why": "Online shoppers can't touch the product. More photos (details, scale, in use) "
               "replace that missing experience.",
        "change": "adding more photos, including the product in use",
        "action": "understand the product before buying", "metric": "conversion rate",
        "fix": ["Aim for at least 4–6 images per product.",
                "Include: front, back/side, close-up detail, product in use, size/scale.",
                "Upload them in Shopify admin → Products → Media."],
        "code": None},
    "description": {
        "title": "Product description", "zone": "description", "mode": "add",
        "why": "A short description leaves questions open. A good one answers what it does, "
               "who it's for and how to use it.",
        "change": "a description built around what it does, who it's for and how to use it",
        "action": "understand what they are buying", "metric": "conversion rate",
        "fix": ["Write the description in four short parts (template below).",
                "Use the real questions customers ask in emails and chats.",
                "Keep paragraphs short and scannable on mobile."],
        "code": "<h3>What it does</h3><p>…</p>\n<h3>Who it's for</h3><p>…</p>\n"
                "<h3>How to use it</h3><p>…</p>\n<h3>What's included</h3><p>…</p>"},
    "variant_labels": {
        "title": "Guidance between options", "zone": "variants", "mode": "add",
        "why": "When there are many options, shoppers hesitate. A simple label like 'Most popular' "
               "helps them decide faster.",
        "change": "adding simple labels such as 'Most popular' and 'Best value'",
        "action": "choose an option faster", "metric": "conversion rate",
        "fix": ["Pick the best-selling option and the best-value option.",
                "Add the label in the variant name (e.g. '2-pack – Most popular') or with a small "
                "badge in the theme code.",
                "Do not change prices at the same time, so you can measure the label's effect."],
        "code": "{% for variant in product.variants %}\n"
                "  {% if variant.title contains '2-pack' %}<span class=\"badge\">Most popular</span>{% endif %}\n"
                "  {% if variant.title contains '4-pack' %}<span class=\"badge\">Best value</span>{% endif %}\n"
                "{% endfor %}"},
    "swatches": {
        "title": "Colour swatches", "zone": "variants", "mode": "add",
        "why": "Choosing a colour from text names is hard. Visual swatches let shoppers pick at "
               "a glance.",
        "change": "visual colour swatches on product and collection pages",
        "action": "pick a colour with less hesitation", "metric": "conversion rate",
        "fix": ["In the theme editor, open the Variant picker block.",
                "Set the style to 'Swatch' (supported by Dawn and many newer themes).",
                "Assign a colour or image to each option value in the product's options."],
        "code": None},
    "sale_savings": {
        "title": "Sale saving shown", "zone": "price", "mode": "add",
        "why": "A discount only works if shoppers notice it. Showing the saving as a percentage "
               "makes the value clear at a glance.",
        "change": "showing the saving as a percentage next to the price",
        "action": "see the value of the offer", "metric": "revenue per visitor",
        "fix": ["Edit code → the price snippet (often snippets/price.liquid).",
                "Add the code below next to the price.",
                "Preview a product that has a compare-at price."],
        "code": "{% if product.compare_at_price > product.price %}\n"
                "  {% assign saving = product.compare_at_price | minus: product.price | times: 100 "
                "| divided_by: product.compare_at_price %}\n"
                "  <span class=\"save-badge\">Save {{ saving }}%</span>\n{% endif %}"},
    "home_trust": {
        "title": "Trust and promises on the homepage", "zone": "trust", "mode": "add",
        "why": "The homepage is where many visitors decide if the store is trustworthy. Ratings "
               "and service promises near the top answer that question immediately.",
        "change": "showing the review rating and key service promises above the fold",
        "action": "trust the store and keep browsing", "metric": "revenue per visitor",
        "fix": ["In the theme editor on the homepage, add a 'Multicolumn' or 'Icon with text' "
                "section right below the hero.",
                "Add your rating (e.g. Trustpilot) and 3 promises: delivery, returns, support.",
                "Keep it to one row on desktop and a swipeable row on mobile."],
        "code": None},
    "home_bundles": {
        "title": "Bundles on the homepage", "zone": "bundles", "mode": "add",
        "why": "Featuring a ready-made bundle on the homepage gives first-time visitors an easy, "
               "good-value place to start.",
        "change": "featuring a best-selling bundle on the homepage",
        "action": "start with a good-value offer", "metric": "revenue per visitor",
        "fix": ["Create a bundle (Shopify Bundles app).",
                "Add a 'Featured product' section on the homepage showing the bundle.",
                "Place it in the first two screens of scrolling."],
        "code": None},
    "home_product_links": {
        "title": "Products reachable from homepage", "zone": "collections", "mode": "add",
        "why": "Visitors should reach products in one click from the homepage. If they can't see "
               "products, many leave.",
        "change": "a best-sellers section with direct product links on the homepage",
        "action": "find a product quickly", "metric": "product page views per visit",
        "fix": ["Add a 'Featured collection' section with your best sellers to the homepage.",
                "Place it high on the page, right after the hero or trust row."],
        "code": None},

    "tracking_ga": {
        "title": "Analytics tracking (GA4)", "zone": "page", "mode": "add",
        "why": "Without reliable analytics you can't see where visitors drop off or measure if a "
               "change worked. CRO starts with trustworthy data.",
        "change": "installing Google Analytics 4 through Shopify's Google & YouTube app",
        "action": "be measured correctly", "metric": "data quality (purchase events recorded)",
        "fix": ["Install the free 'Google & YouTube' app by Google from the Shopify App Store.",
                "Connect your GA4 property in the app.",
                "Make a test purchase and check it appears in GA4 → Realtime.",
                "Note: some stores load GA through Shopify's customer events (web pixels), which "
                "this check can't see. If GA4 already records purchases, ignore this item."],
        "code": None},
    "behavior_tool": {
        "title": "Heatmaps & recordings tool", "zone": "page", "mode": "add",
        "why": "Analytics shows where people leave; heatmaps and recordings show why. Watching "
               "real sessions is the fastest way to find friction.",
        "change": "installing a free heatmap and session-recording tool such as Microsoft Clarity",
        "action": "be understood, not just counted", "metric": "number of friction points found",
        "fix": ["Create a free Microsoft Clarity account and add your store.",
                "Install it with the Clarity app from the Shopify App Store, or paste the "
                "tracking code into theme.liquid before </head>.",
                "Wait a few days, then watch 20 recordings of visitors who didn't buy.",
                "Check the scroll heatmap on your top product page."],
        "code": None},
    # ---------- insights from uploaded analytics data
    "data_overall_cr": {
        "title": "Overall conversion rate", "zone": "chart", "mode": "add",
        "why": "This is the share of visits that end in a purchase. When it is low, the problem "
               "is usually trust, unclear value or friction somewhere in the journey.",
        "change": "researching where visitors drop (session recordings, a short exit survey) and "
                  "fixing the biggest friction first",
        "action": "complete a purchase", "metric": "conversion rate",
        "fix": ["Install a free recording tool (Microsoft Clarity) and watch 20 sessions that "
                "did not buy.",
                "Add a one-question exit survey: 'What stopped you from buying today?'.",
                "Run the website check in this app and fix the red items first.",
                "Compare the conversion rate again after 2–4 weeks."],
        "code": None},
    "data_mobile_gap": {
        "title": "Mobile converts worse than desktop", "zone": "chart", "mode": "add",
        "why": "Most visitors use phones. If they buy much less than desktop visitors, something "
               "on mobile is getting in the way: speed, layout, menu or checkout.",
        "change": "fixing the mobile experience (speed, menu, sticky add-to-cart, checkout)",
        "action": "buy on their phone", "metric": "mobile conversion rate",
        "fix": ["Do a full test purchase on your own phone and write down every annoyance.",
                "Run the mobile speed test in this app and fix the biggest items.",
                "In Microsoft Clarity, filter recordings by 'Mobile' and watch where people stop.",
                "Check the add-to-cart button is visible without scrolling on a small phone."],
        "code": None},
    "data_cart_abandon": {
        "title": "Many carts are abandoned", "zone": "chart", "mode": "add",
        "why": "People who add to cart already want the product. Losing most of them usually "
               "means a surprise later: shipping cost, delivery time or a hard checkout.",
        "change": "showing shipping cost and delivery time before checkout and adding express "
                  "checkout",
        "action": "finish the purchase they started", "metric": "cart-to-purchase rate",
        "fix": ["Show shipping cost and delivery time on the product page and in the cart.",
                "Add a free shipping threshold message in the cart.",
                "Enable Shop Pay / express checkout buttons.",
                "Turn on Shopify's abandoned checkout email (Marketing → Automations)."],
        "code": None},
    "data_checkout_drop": {
        "title": "Drop-off inside checkout", "zone": "chart", "mode": "add",
        "why": "Visitors who reach checkout are very close to buying. Losing many of them points "
               "to forced sign-up, too many fields, missing payment methods or late costs.",
        "change": "making checkout shorter: guest checkout, express payment, no late costs",
        "action": "complete checkout", "metric": "checkout completion rate",
        "fix": ["Settings → Checkout: make customer accounts optional (allow guest checkout).",
                "Enable Shop Pay and the local payment methods your customers expect.",
                "Make sure no new costs appear in checkout that weren't shown before.",
                "Test checkout on mobile from start to finish."],
        "code": None},
    "data_channel_gap": {
        "title": "A traffic source converts poorly", "zone": "chart", "mode": "add",
        "why": "When one channel brings many visits but few sales, the landing page often doesn't "
               "match what the ad or post promised, or the audience is wrong.",
        "change": "sending this traffic to a page that matches the ad's promise",
        "action": "find what they clicked for", "metric": "conversion rate for this channel",
        "fix": ["Open the ads or posts for this channel and note what they promise.",
                "Check the landing page shows exactly that product or offer above the fold.",
                "Send product ads to product pages, not the homepage.",
                "Compare conversion again after the change."],
        "code": None},
    "data_landing_engagement": {
        "title": "Landing page with low engagement", "zone": "chart", "mode": "add",
        "why": "A busy entry page where most visitors leave quickly wastes traffic. Visitors "
               "should understand what you sell and why to buy within a few seconds.",
        "change": "a clearer top section: what it is, why it's good, and one main button",
        "action": "keep browsing instead of leaving", "metric": "engagement rate",
        "fix": ["Open the page on a phone and read only the first screen.",
                "Make sure it says what you sell and shows a main button.",
                "Check speed for this page.",
                "Watch recordings of visitors who left this page."],
        "code": None},
}

REVIEW_APPS = ["judge.me", "judgeme", "yotpo", "okendo", "loox", "stamped", "reviews.io",
               "trustpilot", "shopify-product-reviews", "kudobuzz", "ali-reviews"]
TRUST_WORDS = ["free shipping", "free delivery", "free returns", "money-back", "money back",
               "guarantee", "secure checkout", "warranty", "secure payment"]
SHIPPING_WORDS = ["shipping", "delivery", "dispatch", "ships in", "arrives"]
RETURN_WORDS = ["return", "refund", "exchange"]
LABEL_WORDS = ["best value", "most popular", "best seller", "bestseller"]
BUNDLE_WORDS = ["bundle", "value pack", "frequently bought together", "buy more save",
                "set of", "kit"]
UPSELL_WORDS = ["you may also like", "you might also like", "complete the look", "pairs well",
                "frequently bought together", "recommended for you", "customers also bought",
                "goes well with", "related products"]
FREE_SHIP_BAR = ["away from free shipping", "free shipping on orders over", "free shipping over",
                 "free delivery over", "free delivery on orders over", "for free shipping"]
VIDEO_HINTS = ["<video", "youtube.com/embed", "player.vimeo.com", "tolstoy", "videowise", "tagshop"]
SWATCH_HINTS = ["swatch"]
COLOR_OPTIONS = ["color", "colour", "shade"]
FAST_CHECKOUT = ["shopify-payment-button", "shop-pay", "shop_pay", "dynamic-checkout",
                 "shopify-accelerated-checkout"]


# How each check decides pass / fix (shown in the app so users know what it is based on)
CHECK_RULES = {
    "atc_above_fold": "Real browser audit only. The page is opened as a phone (390×844). Passes if "
                      "the add-to-cart button is fully visible without scrolling.",
    "add_to_cart": "Passes if the product page has Shopify's standard add-to-cart form (/cart/add).",
    "reviews_present": "Passes if a known review app (Judge.me, Yotpo, Okendo, Loox, Stamped, "
                       "Trustpilot…) is found in the product page code.",
    "reviews_position": "With the real browser audit: fixes if reviews start more than two phone "
                        "screens down. Without it: fixes if the first review widget appears after "
                        "the add-to-cart form and in the last third of the page code.",
    "review_volume": "Reads the review count from the page's structured data. Fixes if fewer "
                     "than 5 reviews.",
    "rating_credible": "Fixes if the average rating is 4.9 or higher (with at least 5 reviews).",
    "shipping_info": "Passes if words like shipping, delivery or dispatch appear on the product page.",
    "returns_info": "Passes if words like return, refund or exchange appear on the product page.",
    "trust_signals": "Passes if promises like free shipping, guarantee, warranty or secure "
                     "checkout appear on the product page.",
    "free_ship_bar": "Passes if a message like 'away from free shipping' or 'free shipping over' "
                     "appears on the product page.",
    "bundles": "Passes if words like bundle, kit, set of or 'frequently bought together' appear.",
    "upsell": "Passes if a block like 'You may also like' or 'Related products' appears.",
    "video_ugc": "Passes if a video, YouTube/Vimeo embed or a UGC video app is found.",
    "page_weight": "Fixes if the page loads more than 40 external scripts or its HTML is "
                   "larger than 800 KB.",
    "speed": "Uses Google PageSpeed Insights (mobile). Fixes if the performance score is below 50.",
    "express_checkout": "Passes if Shop Pay or dynamic checkout buttons are found on the product page.",
    "viewport": "Passes if the page has a mobile viewport meta tag.",
    "images": "Reads the product data. Fixes if the product has fewer than 4 images.",
    "description": "Reads the product data. Fixes if the description has fewer than 50 words.",
    "variant_labels": "Only for products with 3+ variants. Passes if labels like 'Most popular' "
                      "or 'Best value' appear.",
    "swatches": "Only for products with a colour option. Passes if swatch elements are found.",
    "sale_savings": "Only for products on sale. Passes if 'save' or a % appears on the page.",
    "home_trust": "Passes if the homepage shows service promises or a Trustpilot widget.",
    "home_bundles": "Passes if the homepage mentions a bundle, kit or set.",
    "home_product_links": "Fixes if the homepage has fewer than 4 direct product links.",
    "tracking_ga": "Passes if Google Analytics or Google Tag Manager code is found on the homepage. "
                   "May miss GA4 installed through Shopify customer events.",
    "behavior_tool": "Passes if Clarity, Hotjar, Mouseflow, Lucky Orange, Crazy Egg, FullStory or "
                     "Contentsquare code is found on the homepage.",
    "data_overall_cr": "From your CSV: purchases ÷ sessions. Fixes if below 1%.",
    "data_mobile_gap": "From your CSV: fixes if mobile conversion is below 60% of desktop conversion.",
    "data_cart_abandon": "From your CSV: purchases ÷ add-to-carts. Fixes if below 25%.",
    "data_checkout_drop": "From your CSV: purchases ÷ checkouts. Fixes if below 50%.",
    "data_channel_gap": "From your CSV: fixes if a channel with 10%+ of visits converts at less "
                        "than half the overall rate.",
    "data_landing_engagement": "From your CSV: fixes if one of the 5 busiest landing pages has an "
                               "engagement rate below 40%.",
}

GLOSSARY = [
    ("CRO (Conversion Rate Optimization)",
     "Improving a store so more of its visitors buy, without needing more traffic."),
    ("Conversion rate", "Share of visits that end in a purchase. 1,000 visits and 20 orders = 2%."),
    ("Revenue per visitor (RPV)", "Revenue divided by visitors. Combines conversion rate and order "
                                  "value, so it shows the real commercial effect of a change."),
    ("Average order value (AOV)", "Average amount spent per order."),
    ("Friction", "Anything that slows shoppers down or makes them doubt: hidden costs, slow pages, "
                 "missing information, a hard checkout."),
    ("Above the fold", "The part of the page visible without scrolling."),
    ("Hypothesis", "A testable idea: 'Because we observed X, we believe Y will help Z, measured by M.'"),
    ("ICE priority", "A quick way to decide what to test first. Each idea gets three scores from "
                     "1 to 10 and the average is its priority:\n"
                     "  • Impact – how much it could improve results\n"
                     "  • Confidence – how sure we are it will work (here: more supporting "
                     "sources = higher confidence)\n"
                     "  • Ease – how easy it is to build\n"
                     "Higher = test sooner. A high score is not a guarantee it will win."),
    ("A/B test", "Half of visitors see the current page (A), half see the changed page (B). "
                 "Compare results to see which works better."),
    ("Statistical significance", "How sure we can be that a difference is real and not luck. "
                                 "CRO teams usually aim for 95%."),
    ("Sample size", "How many visitors a test needs before the result can be trusted."),
    ("Evidence / Sources", "Research and case studies that support a check. You can add or "
                           "remove them in Sources."),
    ("Brief", "A short document for designers and developers: problem, idea, where it goes, "
              "how to build it, how to test it."),
    ("Heatmap / session recording", "Tools like Hotjar or Clarity that show where people click and "
                                    "scroll, and let you watch real visits."),
]

FAQ = [
    ("What does this app do?",
     "It checks a Shopify store against a CRO checklist, explains each issue in plain words and "
     "suggests what to test, with steps to fix it."),
    ("Do I need my own store?",
     "No. You can check any public Shopify store. Uploading analytics data only works with "
     "exports you have access to."),
    ("Is it free?",
     "Yes. Everything runs on your computer. Optional extras: Google's free PageSpeed test, and the "
     "AI add-on, which uses your own API key (or a free local model)."),
    ("How does it work?",
     "See the 'How it works' tab: it collects the pages (or reads your CSV), runs simple rules, "
     "explains and ranks each issue, then gives you visuals, fixes, briefs and reports."),
    ("What is the real browser audit?",
     "With it switched on, the app opens the product page in Chrome or Edge as a phone screen, "
     "waits until everything has loaded, measures where key elements are and takes a screenshot "
     "with numbered markers. It is slower (about 20–40 s) but more accurate."),
    ("Does it use AI?",
     "The checks are simple rules, so results are fast and repeatable. 'Copy AI prompt' gives "
     "you a ready-made question to paste into Claude or another AI assistant."),
    ("How accurate are the results?",
     "Each check reads the page code and text, so a few can be wrong on unusual themes. Treat "
     "results as ideas to test. 'How this was checked' shows the exact rule."),
    ("What does the priority number mean?",
     "It is the ICE score (impact, confidence, ease) from 1 to 10. Higher means test it sooner."),
    ("Where do the percentages in 'Evidence' come from?",
     "From published research and case studies listed in Sources. One store's result does not "
     "guarantee the same result for another."),
    ("What is a source?",
     "A study, article or case study showing that a change on an online store worked or didn't. "
     "Sources appear as evidence under the related checks and push well-supported ideas up the "
     "priority list. They don't change what the app checks."),
    ("What is the AI add-on?",
     "Optional. When you add a source, it can read the page or document for you and list its "
     "findings, whether they support each idea and which checks they relate to. Choose Claude (your own API "
     "key), Google Gemini (free tier with limits) or a free local model (Ollama) with the "
     "'AI add-on' button at the top. You always review the findings before they are saved."),
    ("Can I add my own research?",
     "Yes. Sources → Add: paste a link or pick a PDF or document, write the key finding and "
     "choose which checks it supports."),
    ("Which analytics files can I upload?",
     "CSV exports from Google Analytics 4 or Shopify Analytics with sessions and purchases, "
     "split by device, channel or landing page."),
    ("How do I share the results?",
     "Save report → HTML gives a clean page you can open, print or send. 'Create UX/dev brief' "
     "makes a document for one specific idea."),
    ("How can I get in touch?",
     "Open the 'Contact us' tab, write your message and press 'Send email'."),
    ("Why did a check fail when my store has that feature?",
     "Some apps load content after the page opens. Switch on 'Real browser audit' so the page is "
     "fully loaded before checking. If you still see the feature on the live page, ignore that item."),
]


# ICE prioritisation (impact, ease) – confidence comes from how many sources back the idea.
ICE = {
    "atc_above_fold": (9, 6), "add_to_cart": (10, 7), "reviews_present": (8, 8), "reviews_position": (8, 9),
    "review_volume": (7, 7), "rating_credible": (5, 8), "shipping_info": (8, 9),
    "returns_info": (6, 9), "trust_signals": (7, 9), "free_ship_bar": (6, 7), "bundles": (6, 6),
    "upsell": (6, 7), "video_ugc": (6, 5), "page_weight": (6, 4), "speed": (8, 4),
    "express_checkout": (7, 8), "viewport": (9, 6), "images": (6, 7), "description": (5, 6),
    "variant_labels": (6, 9), "swatches": (5, 6), "sale_savings": (6, 8), "home_trust": (7, 9),
    "home_bundles": (5, 6), "home_product_links": (6, 8), "tracking_ga": (9, 8),
    "behavior_tool": (7, 9), "data_overall_cr": (8, 4), "data_mobile_gap": (9, 5),
    "data_cart_abandon": (9, 6), "data_checkout_drop": (9, 6), "data_channel_gap": (7, 6),
    "data_landing_engagement": (7, 6),
}


def ice_score(check_id, n_sources):
    """n_sources = supporting sources minus sources where the idea did not work."""
    impact, ease = ICE.get(check_id, (5, 5))
    confidence = max(1, min(10, 4 + 2 * n_sources))
    return round((impact + confidence + ease) / 3, 1), impact, confidence, ease


# positive = supports the check's recommendation, negative = contradicts it
EFFECT_PREFIX = {"positive": "", "negative": "Contradicts this idea: ", "no_effect": "No clear effect here: "}


def evidence_items(sources, check_id):
    """Evidence for one check. Sources read with AI give one line per finding; others give
    the finding the user wrote."""
    items = []
    for s in sources:
        found = [f for f in s.get("findings", []) if check_id in f.get("checks", [])]
        if found:
            for f in found:
                items.append({"title": s["title"], "text": f.get("text", ""),
                              "effect": f.get("effect", "positive")})
        elif check_id in s.get("checks", []):
            items.append({"title": s["title"], "text": s.get("finding", ""), "effect": "positive"})
    return items


def evidence_score(sources, check_id):
    score = 0
    for s in sources:
        effects = {f.get("effect", "positive") for f in s.get("findings", [])
                   if check_id in f.get("checks", [])}
        if not effects and check_id in s.get("checks", []):
            effects = {"positive"}
        if "positive" in effects:
            score += 1
        elif "negative" in effects:
            score -= 1
    return score


def evidence_line(item):
    return f"{item['title']}: {EFFECT_PREFIX.get(item['effect'], '')}{item['text']}"


# ================================================================ ANALYSIS

def http_get(url, timeout=20):
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r


def normalize(url):
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    return url


def base_of(url):
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def find_product_url(base, home_html):
    """Try /products.json first; if the store blocks it, look for product links in the HTML."""
    try:
        data = http_get(base + "/products.json?limit=1").json()
        handle = data["products"][0]["handle"]
        return f"{base}/products/{handle}", "first product from the store catalogue"
    except Exception:
        pass
    if home_html:
        soup = BeautifulSoup(home_html, "html.parser")
        for a in soup.select('a[href*="/products/"]'):
            href = a.get("href", "")
            if "/products/" in href:
                return urljoin(base, href.split("?")[0]), "first product linked on the homepage"
    return None, None


def product_json(url):
    clean = url.split("?")[0].rstrip("/")
    try:
        r = requests.get(clean + ".json", headers=HEADERS, timeout=20)
        if r.ok:
            return r.json().get("product")
    except Exception:
        pass
    return None


def review_stats(html):
    count = rating = None
    m = re.search(r'"(?:reviewCount|ratingCount)"\s*:\s*"?(\d+)', html)
    if m:
        count = int(m.group(1))
    m = re.search(r'"ratingValue"\s*:\s*"?([\d.]+)', html)
    if m:
        try:
            rating = round(float(m.group(1)), 2)
        except ValueError:
            pass
    if count is None:
        m = re.search(r'data-number-of-reviews=["\'](\d+)', html)
        if m:
            count = int(m.group(1))
    if rating is None:
        m = re.search(r'data-average-rating=["\']([\d.]+)', html)
        if m:
            try:
                rating = round(float(m.group(1)), 2)
            except ValueError:
                pass
    return count, rating


def pagespeed(url):
    try:
        r = requests.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
                         params={"url": url, "strategy": "mobile", "category": "performance"},
                         timeout=90)
        if r.ok:
            return round(r.json()["lighthouseResult"]["categories"]["performance"]["score"] * 100)
    except Exception:
        pass
    return None


class Page:
    def __init__(self, url, html, size):
        self.url = url
        self.html = html
        self.low = html.lower()
        self.soup = BeautifulSoup(html, "html.parser")
        self.text = self.soup.get_text(" ", strip=True).lower()
        self.size_kb = size // 1024

    def any_text(self, words):
        return any(w in self.text for w in words)

    def any_code(self, words):
        return any(w in self.low for w in words)


def fetch_page(url):
    r = http_get(url)
    return Page(url, r.text, len(r.content))


# ================================================================ REAL BROWSER AUDIT (optional)
# Uses Playwright with the Chrome or Edge already installed on the computer.
# One-time setup:  pip install playwright

MOBILE_VIEW = {"width": 390, "height": 844}
MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
MAX_SHOT_H = 6000
BROWSER_PATH = os.environ.get("CRO_BROWSER_PATH", "")   # optional: path to a Chrome binary


def browser_available():
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except Exception:
        return False


JS_FIND = """() => {
  const vis = el => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return null;
    const s = getComputedStyle(el);
    if (s.visibility === 'hidden' || s.display === 'none' || s.opacity === '0') return null;
    return {x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height};
  };
  const first = sels => {
    for (const s of sels) {
      for (const el of document.querySelectorAll(s)) {
        if (el.closest('header, footer, nav')) continue;
        const b = vis(el); if (b) return b;
      }
    }
    return null;
  };
  const byText = re => {
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = w.nextNode())) {
      if (!re.test(n.textContent)) continue;
      const el = n.parentElement;
      if (!el || el.closest('header, footer, nav, script, style, noscript')) continue;
      const b = vis(el); if (b && b.y > 40) return b;
    }
    return null;
  };
  return {
    title: first(['h1']),
    price: first(['[class*="price"]']),
    atc: first(['form[action*="/cart/add"] button[type="submit"]', 'form[action*="/cart/add"] [name="add"]',
                'button[name="add"]', '[data-add-to-cart]', 'form[action*="/cart/add"] button']),
    express: first(['.shopify-payment-button', 'shopify-accelerated-checkout',
                    '[data-shopify="payment-button"]', 'shop-pay-wallet-button']),
    reviews: first(['.jdgm-widget', '.jdgm-preview-badge', '.jdgm-prev-badge', '.yotpo',
                    '.yotpo-widget-instance', '[data-oke-widget]', '[class*="okendo"]', '.loox-rating',
                    '#looxReviews', '.stamped-product-reviews-badge', '.stamped-main-widget',
                    '[class*="review"]', '[class*="rating"]']),
    shipping: byText(/shipping|delivery|dispatch/i),
    trust: byText(/free shipping|free delivery|guarantee|warranty|secure checkout|free returns/i),
    vh: innerHeight,
    ph: Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)
  };
}"""

JS_OVERLAY = """([marks, vh]) => {
  const root = document.createElement('div');
  root.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:0;z-index:2147483647;pointer-events:none;';
  const fold = document.createElement('div');
  fold.style.cssText = `position:absolute;left:0;top:${vh}px;width:100%;border-top:3px dashed #000;`;
  const fl = document.createElement('div');
  fl.textContent = 'FIRST SCREEN ENDS HERE';
  fl.style.cssText = 'position:absolute;right:6px;top:-24px;background:#000;color:#fff;font:700 11px Arial;padding:3px 7px;';
  fold.appendChild(fl); root.appendChild(fold);
  for (const m of marks) {
    const box = document.createElement('div');
    box.style.cssText = `position:absolute;left:${m.x - 4}px;top:${m.y - 4}px;width:${m.w + 8}px;height:${m.h + 8}px;` +
      `border:3px ${m.bad ? 'solid' : 'dashed'} #000;background:${m.bad ? 'rgba(0,0,0,0.08)' : 'transparent'};`;
    const b = document.createElement('div');
    b.textContent = m.n;
    const bl = m.x < 18 ? 4 : -14;
    b.style.cssText = `position:absolute;left:${bl}px;top:-14px;width:26px;height:26px;border-radius:13px;` +
      `background:${m.bad ? '#000' : '#fff'};color:${m.bad ? '#fff' : '#000'};border:2px solid #000;` +
      'font:700 13px Arial;display:flex;align-items:center;justify-content:center;';
    box.appendChild(b); root.appendChild(box);
    if (m.bad) {
      const ring = document.createElement('div');
      const L = Math.max(2, m.x - 22), R = Math.min(innerWidth - 2, m.x + m.w + 22);
      ring.style.cssText = `position:absolute;left:${L}px;top:${m.y - 18}px;width:${R - L - 8}px;` +
        `height:${m.h + 36}px;border:4px solid #DC2626;border-radius:50%;`;
      root.appendChild(ring);
      b.style.background = '#DC2626'; b.style.borderColor = '#DC2626';
    }
  }
  document.documentElement.appendChild(root);
  const pad = document.createElement('div');
  pad.style.cssText = 'height:70px;background:#fff;';
  document.body.appendChild(pad);
}"""

MARK_LABELS = {"title": "Product title", "price": "Price", "atc": "Add-to-cart button",
               "express": "Express checkout (Shop Pay)", "reviews": "Reviews / star rating",
               "shipping": "Shipping or delivery info", "trust": "Trust promise"}
MARK_CHECKS = {"atc": ["atc_above_fold", "add_to_cart"], "reviews": ["reviews_position",
               "reviews_present", "review_volume", "rating_credible"],
               "shipping": ["shipping_info", "returns_info"], "trust": ["trust_signals", "free_ship_bar"],
               "express": ["express_checkout"], "price": ["sale_savings"]}


def _launch(p):
    errors = []
    attempts = []
    if BROWSER_PATH:
        attempts.append({"executable_path": BROWSER_PATH})
    attempts += [{"channel": "chrome"}, {"channel": "msedge"}, {}]
    for kw in attempts:
        try:
            return p.chromium.launch(headless=True, **kw)
        except Exception as e:
            errors.append(str(e).splitlines()[0][:120])
    raise RuntimeError("No browser found. Install Google Chrome or Microsoft Edge, or run "
                       "'python -m playwright install chromium'.\n" + "\n".join(errors))


def render_audit(url, out_dir):
    from playwright.sync_api import sync_playwright
    out_dir.mkdir(parents=True, exist_ok=True)
    host = urlparse(url).netloc.replace(":", "_") or "page"
    import time
    shot = out_dir / f"{host}_{int(time.time())}.png"
    with sync_playwright() as p:
        browser = _launch(p)
        try:
            ctx = browser.new_context(viewport=MOBILE_VIEW, device_scale_factor=1, is_mobile=True,
                                      has_touch=True, user_agent=MOBILE_UA)
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            try:
                page.wait_for_load_state("networkidle", timeout=12000)
            except Exception:
                pass
            # scroll down and back so lazy-loaded parts (like review widgets) appear
            page.evaluate("""async () => {
                for (let y = 0; y < Math.min(document.body.scrollHeight, 9000); y += 700) {
                    window.scrollTo(0, y); await new Promise(r => setTimeout(r, 120)); }
                window.scrollTo(0, 0); }""")
            page.wait_for_timeout(1200)
            try:
                page.keyboard.press("Escape")       # closes many pop-ups
            except Exception:
                pass
            found = page.evaluate(JS_FIND)
            html = page.content()
            vh = found.get("vh") or MOBILE_VIEW["height"]
            marks, legend = [], []
            n = 0
            for key in ["title", "price", "reviews", "atc", "express", "trust", "shipping"]:
                b = found.get(key)
                if not b:
                    legend.append({"n": None, "key": key, "label": MARK_LABELS[key],
                                   "status": "not found on the page", "bad": key in ("atc", "reviews")})
                    continue
                dup = next((m for m in marks if abs(m["x"] - b["x"]) < 2 and abs(m["y"] - b["y"]) < 2), None)
                if dup:                      # same element found twice (e.g. one line with shipping
                    legend.append({"n": dup["n"], "key": key, "label": MARK_LABELS[key],   # and a promise)
                                   "status": f"same place as marker {dup['n']}", "bad": False,
                                   "y": b["y"]})
                    continue
                n += 1
                screens = b["y"] / vh
                bad = False
                if b["y"] + b["h"] <= vh:
                    status = "on the first screen"
                elif b["y"] < vh:
                    status = "cut off at the bottom of the first screen"
                else:
                    status = f"below the first screen ({screens:.1f} screens down)"
                if key == "atc" and b["y"] + b["h"] > vh:
                    bad = True
                if key == "reviews" and b["y"] > 2 * vh:
                    bad = True
                marks.append({"n": n, "x": b["x"], "y": b["y"], "w": b["w"], "h": b["h"], "bad": bad})
                legend.append({"n": n, "key": key, "label": MARK_LABELS[key], "status": status,
                               "bad": bad, "y": b["y"]})
            page.evaluate(JS_OVERLAY, [marks, vh])
            full_h = page.evaluate("Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
            ph = min(full_h or vh, MAX_SHOT_H)
            page.screenshot(path=str(shot), full_page=True,
                            clip={"x": 0, "y": 0, "width": MOBILE_VIEW["width"], "height": ph})
        finally:
            browser.close()
    return {"html": html, "shot": str(shot), "found": found, "vh": vh, "legend": legend,
            "url": url, "cut": (found.get("ph") or 0) > MAX_SHOT_H}


def analyze(url, with_speed, progress, with_browser=False):
    url = normalize(url)
    base = base_of(url)
    results, notes = [], []

    def add(check_id, passed, observation, page_label, detail=""):
        results.append({"id": check_id, "page": page_label, "passed": bool(passed),
                        "observation": observation, "detail": detail})

    # ---------- homepage
    progress("Loading the homepage…")
    home = None
    try:
        home = fetch_page(base + "/")
    except Exception as e:
        notes.append(f"Homepage could not be loaded ({e.__class__.__name__}).")

    if home:
        if "cdn.shopify.com" not in home.low and "shopify" not in home.low:
            notes.append("This store may not be on Shopify. Results can be less accurate.")
        add("home_trust", home.any_text(TRUST_WORDS) or home.any_code(["trustpilot"]),
            "no rating or service promises (shipping, returns, guarantee) on the homepage",
            "Homepage")
        add("home_bundles", home.any_text(BUNDLE_WORDS),
            "no bundle or set featured on the homepage", "Homepage")
        n_links = len(home.soup.select('a[href*="/products/"]'))
        add("home_product_links", n_links >= 4,
            f"only {n_links} direct product link(s) on the homepage", "Homepage",
            f"{n_links} product links")
        add("viewport", home.soup.find("meta", attrs={"name": "viewport"}) is not None,
            "no mobile viewport setting, so the page may not fit phone screens", "Homepage")
        add("tracking_ga", home.any_code(["googletagmanager.com", "gtag(", "google-analytics.com",
                                          "g-"]) and home.any_code(["googletagmanager", "gtag"]),
            "no Google Analytics / Tag Manager code on the homepage", "Homepage")
        add("behavior_tool", home.any_code(["clarity.ms", "hotjar", "mouseflow", "luckyorange",
                                            "crazyegg", "fullstory", "contentsquare"]),
            "no heatmap or session-recording tool (Clarity, Hotjar…) on the homepage", "Homepage")
        n_js = len(home.soup.find_all("script", src=True))
        add("page_weight", n_js <= 40 and home.size_kb <= 800,
            f"a heavy homepage with {n_js} external scripts and {home.size_kb} KB of HTML",
            "Homepage", f"{n_js} scripts, {home.size_kb} KB")

    # ---------- product page
    if "/products/" in url:
        product_url, how = url, "the link you entered"
    else:
        progress("Looking for a product page…")
        product_url, how = find_product_url(base, home.html if home else None)

    prod = None
    audit = None
    if product_url:
        progress("Loading the product page…")
        try:
            prod = fetch_page(product_url)
            notes.append(f"Product page checked: {product_url} ({how}).")
        except Exception as e:
            notes.append(f"Product page could not be loaded ({e.__class__.__name__}).")
        if with_browser:
            progress("Opening the page in a real mobile browser…")
            try:
                audit = render_audit(product_url, DATA_DIR / "screenshots")
                prod = Page(product_url, audit["html"], len(audit["html"].encode("utf-8")))
                notes.append("Real browser audit: the page was opened as a phone (390×844) and "
                             "measured after it fully loaded.")
            except Exception as e:
                notes.append(f"Real browser audit could not run: {str(e).splitlines()[0][:160]}")
    else:
        notes.append("No product page found, so only the homepage was checked.")

    if prod:
        P = "Product page"
        pj = product_json(product_url)
        if not pj:
            notes.append("Product data (.json) was not available; image, description and "
                         "variant checks were skipped.")

        add("add_to_cart", prod.soup.select_one('form[action*="/cart/add"]') is not None,
            "no standard add-to-cart form on the product page", P)

        f = audit["found"] if audit else {}
        vh = audit["vh"] if audit else 0
        if audit and f.get("atc"):
            atc_b = f["atc"]
            add("atc_above_fold", atc_b["y"] + atc_b["h"] <= vh,
                "that on a phone the add-to-cart button is not fully visible until the visitor "
                "scrolls", P,
                "first screen" if atc_b["y"] + atc_b["h"] <= vh else "needs scrolling")
        has_reviews = prod.any_code(REVIEW_APPS) or bool(f.get("reviews"))
        add("reviews_present", has_reviews, "no review app or star rating on the product page", P)
        if has_reviews and audit and f.get("reviews"):
            rv = f["reviews"]
            add("reviews_position", rv["y"] <= 2 * vh,
                f"that reviews start about {rv['y'] / vh:.1f} phone screens down, where many "
                f"visitors never scroll", P, f"{rv['y'] / vh:.1f} screens down")
        elif has_reviews:
            first = min(prod.low.find(a) for a in REVIEW_APPS if a in prod.low)
            atc = prod.low.find("/cart/add")
            late = atc != -1 and first > atc and (first / max(len(prod.low), 1)) > 0.66
            add("reviews_position", not late,
                "reviews sit far below the add-to-cart button, where many visitors don't scroll", P)

        count, rating = review_stats(prod.html)
        if count is not None:
            add("review_volume", count >= 5, f"only {count} review(s) on the product", P,
                f"{count} reviews")
            if rating is not None and count >= 5:
                add("rating_credible", rating < 4.9,
                    f"a near-perfect {rating} rating, which can look too good to be true", P,
                    f"rating {rating}")

        add("shipping_info", prod.any_text(SHIPPING_WORDS),
            "no shipping or delivery information on the product page", P)
        add("returns_info", prod.any_text(RETURN_WORDS),
            "no returns or refund information on the product page", P)
        add("trust_signals", prod.any_text(TRUST_WORDS),
            "no service promises such as free shipping or a guarantee near the price", P)
        add("free_ship_bar", prod.any_text(FREE_SHIP_BAR),
            "no message telling shoppers how much more to spend for free shipping", P)
        add("bundles", prod.any_text(BUNDLE_WORDS), "no bundle or set offered on the product page", P)
        add("upsell", prod.any_text(UPSELL_WORDS), "no related products or upsell on the product page", P)
        add("video_ugc", prod.any_code(VIDEO_HINTS), "no product video or customer-made content", P)
        add("express_checkout", prod.any_code(FAST_CHECKOUT),
            "no express checkout option such as Shop Pay on the product page", P)
        n_js = len(prod.soup.find_all("script", src=True))
        add("page_weight", n_js <= 40 and prod.size_kb <= 800,
            f"a heavy product page with {n_js} external scripts and {prod.size_kb} KB of HTML",
            P, f"{n_js} scripts, {prod.size_kb} KB")

        if pj:
            n_img = len(pj.get("images", []))
            add("images", n_img >= 4, f"only {n_img} product image(s)", P,
                f"{n_img} image{'' if n_img == 1 else 's'}")
            desc = BeautifulSoup(pj.get("body_html") or "", "html.parser").get_text(" ", strip=True)
            words = len(desc.split())
            add("description", words >= 50, f"a very short product description ({words} word{'' if words == 1 else 's'})",
                P, f"{words} word{'' if words == 1 else 's'}")
            variants = pj.get("variants", [])
            if len(variants) >= 3:
                add("variant_labels", prod.any_text(LABEL_WORDS),
                    f"{len(variants)} options with no label like 'Most popular' or 'Best value'",
                    P, f"{len(variants)} variants")
            opts = [o.get("name", "").lower() for o in pj.get("options", [])]
            if any(c in o for o in opts for c in COLOR_OPTIONS):
                add("swatches", prod.any_code(SWATCH_HINTS),
                    "colour options shown as text without visual swatches", P)
            try:
                on_sale = any(float(v.get("compare_at_price") or 0) > float(v.get("price") or 0)
                              for v in variants)
            except (TypeError, ValueError):
                on_sale = False
            if on_sale:
                add("sale_savings", "save" in prod.text or "%" in prod.text,
                    "a sale price without a clear saving shown", P)

    # ---------- speed
    if with_speed:
        target = product_url if prod else (base + "/" if home else None)
        if target:
            progress("Running Google mobile speed test (up to a minute)…")
            score = pagespeed(target)
            if score is not None:
                add("speed", score >= 50, f"a low mobile speed score of {score}/100",
                    "Product page" if prod else "Homepage", f"{score}/100")
            else:
                notes.append("Speed test was not available right now; try again later.")

    if not results:
        raise RuntimeError("Nothing could be checked. Is the link correct and the site online?")
    return results, notes, audit


def hypothesis(r):
    c = CHECKS[r["id"]]
    return (f"Because we observed {r['observation']}, we believe {c['change']} will help "
            f"visitors {c['action']}, measured by {c['metric']}.")


def ai_prompt(r, url):
    c = CHECKS[r["id"]]
    return (f"I run a Shopify store ({url}). A CRO check found: {r['observation']}.\n"
            f"I want to fix it by {c['change']}.\n"
            f"Please give me step-by-step instructions for the Shopify admin and, if needed, "
            f"Liquid/HTML/CSS code I can paste into my theme. Tell me exactly which file and "
            f"where to paste it, and how to test it on mobile. Keep it simple; I'm a beginner.")




# ================================================================ ANALYTICS DATA (CSV)

import csv
import io

COLS = {
    "sessions": ["sessions", "visits", "total sessions"],
    "users": ["total users", "active users", "users", "visitors"],
    "purchases": ["ecommerce purchases", "purchases", "transactions", "orders",
                  "sessions that completed checkout", "sessions converted", "completed checkout",
                  "key events", "conversions"],
    "revenue": ["purchase revenue", "total revenue", "revenue", "total sales", "net sales",
                "gross sales"],
    "atc": ["add to carts", "add-to-carts", "adds to cart", "add_to_cart",
            "sessions with cart additions", "added to cart"],
    "checkout": ["checkouts", "begin checkout", "begin_checkout", "sessions that reached checkout",
                 "reached checkout"],
    "engagement": ["engagement rate"],
    "bounce": ["bounce rate"],
}
TOTAL_ROWS = {"grand total", "total", "totals"}


def to_num(v):
    if v is None:
        return None
    t = str(v).strip().replace(" ", "").replace(" ", "")
    pct = t.endswith("%")
    t = re.sub(r"[^\d.,\-]", "", t)
    if not t:
        return None
    if "," in t and "." in t:
        t = t.replace(",", "")
    elif "," in t:
        t = t.replace(",", "") if len(t.split(",")[-1]) == 3 else t.replace(",", ".")
    try:
        x = float(t)
    except ValueError:
        return None
    return x / 100 if pct else x


def read_tables(path):
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    lines = [l for l in text.splitlines() if not l.lstrip().startswith("#")]
    blocks, cur = [], []
    for l in lines:
        if l.strip() == "":
            if cur:
                blocks.append(cur)
                cur = []
        else:
            cur.append(l)
    if cur:
        blocks.append(cur)
    tables = []
    for b in blocks:
        if len(b) < 2:
            continue
        sample = "\n".join(b[:3])
        delim = ";" if sample.count(";") > sample.count(",") else ("\t" if "\t" in sample else ",")
        rows = list(csv.reader(io.StringIO("\n".join(b)), delimiter=delim))
        header = [h.strip() for h in rows[0]]
        data = [dict(zip(header, r)) for r in rows[1:] if any(c.strip() for c in r)]
        if data and len(header) >= 2:
            tables.append((header, data))
    return tables


def find_col(header, key):
    low = {h.lower(): h for h in header}
    for name in COLS[key]:                       # exact match first
        if name in low:
            return low[name]
    for name in COLS[key]:                       # then 'starts with'
        for l, h in low.items():
            if l.startswith(name):
                return h
    return None


def dim_kind(name):
    n = name.lower()
    if "device" in n:
        return "device"
    if any(k in n for k in ["channel", "source", "medium", "referrer", "utm"]):
        return "channel"
    if any(k in n for k in ["landing", "page path", "page title", "page", "screen"]):
        return "landing"
    return "other"


def pct(x):
    return f"{x * 100:.1f}%"


def analyze_data(path):
    tables = read_tables(path)
    if not tables:
        raise RuntimeError("No table found in this file. Export the report as CSV and try again.")
    results, notes = [], [f"Analytics file: {Path(path).name} ({len(tables)} table(s) found)."]
    P = "Your data"

    def add(cid, passed, obs, detail="", chart=None, chart_title=""):
        results.append({"id": cid, "page": P, "passed": bool(passed), "observation": obs,
                        "detail": detail, "chart": chart, "chart_title": chart_title})

    totals = {}
    used = set()
    for header, rows in tables:
        dim = header[0]
        cols = {k: find_col(header, k) for k in COLS}
        base = cols["sessions"] or cols["users"]
        rows = [r for r in rows if str(r.get(dim, "")).strip().lower() not in TOTAL_ROWS]
        if not base or not rows:
            continue
        for k in ("sessions", "users", "purchases", "revenue", "atc", "checkout"):
            if cols[k] and k not in totals:
                totals[k] = sum(to_num(r.get(cols[k])) or 0 for r in rows)

        kind = dim_kind(dim)
        seg = []
        for r in rows:
            v = to_num(r.get(base)) or 0
            if v <= 0:
                continue
            item = {"name": str(r.get(dim, "")).strip() or "(not set)", "visits": v}
            if cols["purchases"]:
                item["cr"] = (to_num(r.get(cols["purchases"])) or 0) / v
            if cols["revenue"]:
                item["rpv"] = (to_num(r.get(cols["revenue"])) or 0) / v
            if cols["engagement"]:
                item["eng"] = to_num(r.get(cols["engagement"]))
            elif cols["bounce"]:
                b = to_num(r.get(cols["bounce"]))
                item["eng"] = None if b is None else 1 - b
            seg.append(item)
        if not seg:
            continue
        total_v = sum(i["visits"] for i in seg)

        if kind == "device" and "cr" in seg[0] and "device" not in used:
            used.add("device")
            mob = next((i for i in seg if "mobile" in i["name"].lower()), None)
            desk = next((i for i in seg if "desktop" in i["name"].lower()), None)
            chart = [(i["name"], i["cr"], i is mob) for i in seg]
            if mob and desk and desk["cr"] > 0:
                ratio = mob["cr"] / desk["cr"]
                add("data_mobile_gap", ratio >= 0.6,
                    f"mobile converts at {pct(mob['cr'])} vs. {pct(desk['cr'])} on desktop "
                    f"({ratio * 100:.0f}% of desktop), while mobile brings "
                    f"{mob['visits'] / total_v * 100:.0f}% of visits",
                    f"mobile {pct(mob['cr'])} vs desktop {pct(desk['cr'])}",
                    chart, "Conversion rate by device")

        if kind == "channel" and "cr" in seg[0] and "channel" not in used:
            used.add("channel")
            overall = sum(i["cr"] * i["visits"] for i in seg) / total_v
            big = [i for i in seg if i["visits"] / total_v >= 0.10]
            worst = min(big, key=lambda i: i["cr"]) if big else None
            if worst and overall > 0:
                chart = [(i["name"], i["cr"], i is worst) for i in
                         sorted(seg, key=lambda i: -i["visits"])[:8]]
                add("data_channel_gap", worst["cr"] >= overall * 0.5,
                    f"'{worst['name']}' brings {worst['visits'] / total_v * 100:.0f}% of visits but "
                    f"converts at {pct(worst['cr'])}, against {pct(overall)} overall",
                    f"{worst['name']}: {pct(worst['cr'])}", chart, "Conversion rate by channel")

        if kind == "landing" and any(i.get("eng") is not None for i in seg) and "landing" not in used:
            used.add("landing")
            top = sorted(seg, key=lambda i: -i["visits"])[:8]
            weak = [i for i in top[:5] if i.get("eng") is not None and i["eng"] < 0.40]
            chart = [(i["name"][:40], i.get("eng") or 0, i in weak) for i in top]
            w = weak[0] if weak else None
            add("data_landing_engagement", not weak,
                (f"'{w['name']}' is one of your busiest entry pages, but only {pct(w['eng'])} of "
                 f"its visits are engaged" if w else "your busiest entry pages engage visitors well"),
                (f"{w['name'][:30]}: {pct(w['eng'])}" if w else ""),
                chart, "Engagement rate of top landing pages")

    # funnel from totals
    s_ = totals.get("sessions") or totals.get("users")
    if s_ and totals.get("purchases") is not None:
        cr = totals["purchases"] / s_
        add("data_overall_cr", cr >= 0.01, f"an overall conversion rate of {pct(cr)}",
            pct(cr), [("Visits → purchase", cr, cr < 0.01)], "Overall conversion rate")
    if totals.get("atc") and totals.get("purchases") is not None:
        rate = totals["purchases"] / totals["atc"]
        steps = [("Added to cart", 1.0, False)]
        if totals.get("checkout"):
            steps.append(("Reached checkout", totals["checkout"] / totals["atc"], False))
        steps.append(("Purchased", rate, rate < 0.25))
        add("data_cart_abandon", rate >= 0.25,
            f"only {pct(rate)} of add-to-carts end in a purchase", f"{pct(rate)} of carts buy",
            steps, "Share of carts that move to each step")
    if totals.get("checkout") and totals.get("purchases") is not None:
        rate = totals["purchases"] / totals["checkout"]
        add("data_checkout_drop", rate >= 0.5,
            f"only {pct(rate)} of checkouts are completed", f"{pct(rate)} complete",
            [("Reached checkout", 1.0, False), ("Completed", rate, rate < 0.5)],
            "Checkout completion")

    if not results:
        raise RuntimeError(
            "The file was read, but it doesn't have the columns needed (for example Sessions and "
            "Purchases, split by device, channel or landing page). See 'How to export' for tips.")
    notes.append("Thresholds are rules of thumb for spotting problems, not industry benchmarks.")
    return results, notes


def draw_chart(cv, r):
    data = r.get("chart") or []
    title = r.get("chart_title", "")
    cv.create_text(350, 22, text=title, font=(FONT, 14, "bold"), fill=C["text"])
    top, left, bar_w = 70, 210, 380
    mx = max([v for _, v, _ in data] + [1e-9])
    for i, (label, v, flag) in enumerate(data):
        y = top + i * 46
        cv.create_text(left - 12, y + 14, text=str(label)[:30], anchor="e", font=(FONT, 10),
                       fill=C["text"])
        w = max(3, bar_w * v / mx)
        cv.create_rectangle(left, y, left + w, y + 28, fill="#0A0A0A" if flag else "#C7C7C7",
                            outline="")
        cv.create_text(left + w + 8, y + 14, text=pct(v), anchor="w",
                       font=(FONT, 10, "bold"), fill=C["bad"] if flag else C["text"])
        if flag:
            cv.create_oval(left - 150, y - 10, left + w + 64, y + 38, outline=MARK, width=3)
    h = top + len(data) * 46 + 10
    cv.create_rectangle(left, h, left + 14, h + 14, fill="#0A0A0A", outline="")
    cv.create_text(left + 22, h + 7, text="needs attention", anchor="w", font=(FONT, 9),
                   fill=C["muted"])
    return h + 30


EXPORT_HELP = (
    "How to export data as CSV\n\n"
    "Google Analytics 4\n"
    "1. Reports → Tech → Tech details: change the dimension to 'Device category'.\n"
    "   Or Reports → Acquisition → Traffic acquisition (channels),\n"
    "   or Reports → Engagement → Landing page.\n"
    "2. Make sure the table shows Sessions and (Ecommerce) purchases or Key events.\n"
    "3. Click the Share icon (top right) → Download file → Download CSV.\n\n"
    "Shopify Analytics\n"
    "Analytics → Reports → e.g. 'Sessions by device type' or 'Online store conversion over "
    "time' → Export → CSV.\n\n"
    "You can upload several files one after another; each one adds its findings to the list.")


# ================================================================ AI ADD-ON (optional, your own key)
# Reads a source (web page, PDF, Word, text) and asks an AI model to pull out concrete CRO
# findings, whether they worked, and which checks they relate to. The user reviews the result.

SETTINGS_FILE = DATA_DIR / "settings.json"
AI_PROVIDERS = {
    "claude": {"name": "Claude (Anthropic)", "tag": "Recommended · paid, your own API key",
               "models": ["claude-haiku-5-5", "claude-sonnet-5-5"],
               "key_url": "https://console.anthropic.com/",
               "note": "Best at reading reports carefully. You pay Anthropic directly for what you "
                       "use; reading one document usually costs very little."},
    "gemini": {"name": "Google Gemini", "tag": "Free tier with limits · your own API key",
               "models": ["gemini-flash-latest", "gemini-flash-lite-latest"],
               "key_url": "https://aistudio.google.com/apikey",
               "note": "Free tier has daily limits and Google may use free-tier content to improve "
                       "its products. In the EU, apps that serve other users must use the paid tier."},
    "ollama": {"name": "Local model (Ollama)", "tag": "Free · private · runs on your computer",
               "models": ["qwen2.5:7b", "llama3.1:8b", "llama3.2:3b"],
               "key_url": "https://ollama.com/download",
               "note": "Nothing leaves your computer. Needs about 16 GB of RAM for good results and "
                       "is slower. Install Ollama, then run e.g. 'ollama pull qwen2.5:7b'."},
}
DEFAULT_SETTINGS = {"provider": "claude", "claude_key": "", "claude_model": "claude-haiku-5-5",
                    "gemini_key": "", "gemini_model": "gemini-flash-latest",
                    "ollama_url": "http://localhost:11434", "ollama_model": "qwen2.5:7b"}


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    try:
        if SETTINGS_FILE.exists():
            s.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
    except Exception:
        pass
    return s


def save_settings(settings):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def ai_ready(settings):
    p = settings.get("provider")
    if p == "ollama":
        return True
    return bool(settings.get(f"{p}_key", "").strip())


def pip_install(package):
    import subprocess
    flags = 0x08000000 if sys.platform.startswith("win") else 0
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        exe = exe[:-5] + ".exe"
    try:
        r = subprocess.run([exe, "-m", "pip", "install", package], capture_output=True, text=True,
                           creationflags=flags, timeout=900)
        return r.returncode == 0, (r.stderr or r.stdout)[-600:]
    except Exception as e:
        return False, str(e)


def pdf_text(data):
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError("NEEDS_PYPDF")
    import io as _io
    reader = PdfReader(_io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages[:80])


def docx_text(data):
    import zipfile
    import io as _io
    with zipfile.ZipFile(_io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml)


def read_source_text(loc):
    """Returns (title, text) for a link or a local file."""
    title = ""
    if loc.startswith("http"):
        r = requests.get(loc, headers=HEADERS, timeout=40)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "").lower()
        if "pdf" in ctype or loc.lower().split("?")[0].endswith(".pdf"):
            text = pdf_text(r.content)
            title = Path(urlparse(loc).path).stem
        else:
            soup = BeautifulSoup(r.text, "html.parser")
            title = soup.title.get_text(strip=True) if soup.title else urlparse(loc).netloc
            for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "form"]):
                tag.decompose()
            main = soup.find("article") or soup.find("main") or soup.body or soup
            text = main.get_text("\n", strip=True)
    else:
        path = Path(loc)
        if not path.exists():
            raise RuntimeError("File not found.")
        data = path.read_bytes()
        title = path.stem
        ext = path.suffix.lower()
        if ext == ".pdf":
            text = pdf_text(data)
        elif ext == ".docx":
            text = docx_text(data)
        elif ext in (".txt", ".md", ".csv", ".html", ".htm"):
            text = data.decode("utf-8", "ignore")
            if ext in (".html", ".htm"):
                text = BeautifulSoup(text, "html.parser").get_text("\n", strip=True)
        else:
            raise RuntimeError("Unsupported file type. Use a link, PDF, Word (.docx) or text file.")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) < 200:
        raise RuntimeError("Very little readable text was found in this source.")
    return title, text[:60000]


def build_ai_prompt(title, text):
    checks = "\n".join(f"- {cid}: {c['title']}. Our recommendation: {c['change']}."
                       for cid, c in CHECKS.items())
    return f"""You are a conversion rate optimisation (CRO) analyst. Read the document below and
extract concrete findings about what changes affect online-store results (conversion rate,
revenue per visitor, average order value, cart or checkout completion, engagement).

Rules:
- Only use what the document actually says. Never invent or round numbers.
- Write each finding as one short, plain-English sentence that includes the numbers given.
- checks: ids from the list below whose recommendation the finding is about. Use [] if none fit.
- stance: compare the finding with the recommendation of those checks:
  "supports" if it shows that following the recommendation helps (this includes findings where
  doing the opposite hurt results), "contradicts" if it shows that following the recommendation
  did not help or hurt, "no_effect" if the document says it made no clear difference.
- confidence: "high" if the document reports measured results (e.g. an A/B test or study),
  "medium" for surveys or expert claims, "low" for opinions.
- Leave out general advice without evidence. Return at most 12 findings.

Checks:
{checks}

Return only JSON in this exact shape:
{{"title": "short title of the document", "summary": "one-sentence summary",
  "findings": [{{"text": "...", "stance": "supports", "checks": ["id"], "confidence": "high"}}]}}

Document title: {title}
Document:
\"\"\"
{text}
\"\"\""""


def call_ai(settings, prompt, max_tokens=4000):
    p = settings.get("provider", "claude")
    if p == "claude":
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=180,
                          headers={"x-api-key": settings["claude_key"].strip(),
                                   "anthropic-version": "2023-06-01",
                                   "content-type": "application/json"},
                          json={"model": settings["claude_model"], "max_tokens": max_tokens,
                                "messages": [{"role": "user", "content": prompt}]})
        data = r.json() if r.content else {}
        if r.status_code != 200:
            raise RuntimeError(f"Claude API error ({r.status_code}): "
                               f"{data.get('error', {}).get('message', r.text[:200])}")
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    if p == "gemini":
        model = settings["gemini_model"].strip()
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                          timeout=180,
                          headers={"x-goog-api-key": settings["gemini_key"].strip(),
                                   "content-type": "application/json"},
                          json={"contents": [{"parts": [{"text": prompt}]}],
                                "generationConfig": {"responseMimeType": "application/json",
                                                     "maxOutputTokens": max_tokens}})
        data = r.json() if r.content else {}
        if r.status_code != 200:
            raise RuntimeError(f"Gemini API error ({r.status_code}): "
                               f"{data.get('error', {}).get('message', r.text[:200])}")
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        return "".join(x.get("text", "") for x in parts)
    if p == "ollama":
        base = settings.get("ollama_url", "http://localhost:11434").rstrip("/")
        try:
            r = requests.post(f"{base}/api/chat", timeout=900,
                              json={"model": settings["ollama_model"], "stream": False,
                                    "format": "json",
                                    "messages": [{"role": "user", "content": prompt}]})
        except requests.ConnectionError:
            raise RuntimeError("Ollama is not running. Install it from ollama.com and start it.")
        if r.status_code != 200:
            raise RuntimeError(f"Ollama error ({r.status_code}): {r.text[:200]}")
        return r.json().get("message", {}).get("content", "")
    raise RuntimeError("Unknown AI provider.")


def parse_ai_json(text):
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b == -1:
        raise RuntimeError("The AI answer was not in the expected format. Try again.")
    return json.loads(text[a:b + 1])


def ai_extract(settings, loc):
    title, text = read_source_text(loc)
    data = parse_ai_json(call_ai(settings, build_ai_prompt(title, text)))
    findings = []
    for f in data.get("findings", [])[:12]:
        t = str(f.get("text", "")).strip()
        if not t:
            continue
        stance = str(f.get("stance", f.get("effect", "supports"))).lower().replace(" ", "_")
        effect = {"supports": "positive", "positive": "positive", "contradicts": "negative",
                  "negative": "negative", "no_effect": "no_effect"}.get(stance, "positive")
        checks = [c for c in f.get("checks", []) if c in CHECKS]
        findings.append({"text": t, "effect": effect, "checks": checks,
                         "confidence": str(f.get("confidence", "medium")).lower()})
    return {"title": str(data.get("title") or title)[:120], "summary": str(data.get("summary", "")),
            "findings": findings}


# ================================================================ VISUAL SKETCH

PRODUCT_LAYOUT = [("header", "Header / menu", 30), ("hero", "Product images", 120),
                  ("price", "Title + price", 38), ("reviews_top", "★★★★☆  Reviews", 28),
                  ("variants", "Options", 34), ("atc", "Add to cart", 36),
                  ("trust", "Promises / free shipping", 28), ("shipping", "Shipping · Returns", 28),
                  ("bundles", "Bundle offer", 34), ("description", "Description", 50),
                  ("recs", "You may also like", 42), ("reviews_bottom", "Reviews (bottom)", 30)]
HOME_LAYOUT = [("header", "Header / menu", 34), ("hero", "Hero banner", 130),
               ("trust", "Rating + promises", 34), ("bundles", "Featured bundle", 60),
               ("collections", "Best sellers", 100), ("content", "Brand story", 70),
               ("footer", "Footer", 36)]


# What the new element looks like in the "Suggested" sketch
VISUAL_LABEL = {
    "add_to_cart": "[  Add to cart  ]",
    "reviews_present": "★★★★☆ 4.6 · 128 reviews",
    "reviews_position": "★★★★☆ 4.6 · 128 reviews",
    "review_volume": "★★★★☆ 4.5 · 42 reviews",
    "rating_credible": "★★★★☆ 4.6 · Verified buyers",
    "shipping_info": "🚚 Ships in 1–2 days · €4.90",
    "returns_info": "↩ 30-day free returns",
    "trust_signals": "Free shipping · Returns · Secure",
    "free_ship_bar": "€12 away from free shipping ▓▓▓▓░",
    "bundles": "Bundle: buy 2, save 15%",
    "upsell": "Goes well with ▢ ▢ ▢",
    "video_ugc": "▶ Customer video",
    "express_checkout": "[ Shop Pay ]  [ Buy now ]",
    "atc_above_fold": "[  Add to cart  ]",
    "images": "▢ ▢ ▢ ▢ ▢  more photos",
    "description": "What it does · Who for · How to use",
    "variant_labels": "2-pack  MOST POPULAR",
    "swatches": "● ● ● ●  colour swatches",
    "sale_savings": "€29  €39  SAVE 25%",
    "home_trust": "★ 4.7 · Free shipping · Returns",
    "home_bundles": "Starter bundle · save 20%",
    "home_product_links": "Best sellers  ▢ ▢ ▢ ▢",
}

PHONE_W = 240


def phone_frame(cv, x, y, h, border):
    cv.create_rectangle(x - 8, y - 8, x + PHONE_W + 8, y + h + 8, fill=border, outline="")
    cv.create_rectangle(x, y, x + PHONE_W, y + h, fill="#FFFFFF", outline="")


def block(cv, x, cy, h, label, kind):
    styles = {"normal": ("#F0F0F0", "#F0F0F0", C["muted"]),
              "atc": (C["navy2"], C["navy2"], "#FFFFFF"),
              "new": (C["hl_bg"], C["hl"], C["text"]),
              "have": (C["hl_bg"], C["hl"], C["text"]),
              "bad": ("#FFFFFF", C["text"], C["text"])}
    fill, out, color = styles[kind]
    cv.create_rectangle(x + 10, cy, x + PHONE_W - 10, cy + h, fill=fill, outline=out,
                        width=3 if kind in ("new", "have") else 2,
                        dash=(5, 3) if kind == "bad" else None)
    cv.create_text(x + PHONE_W / 2, cy + h / 2, text=label, fill=color,
                   font=(FONT, 9, "bold" if kind in ("new", "have", "bad") else "normal"),
                   width=PHONE_W - 30)
    if kind in ("new", "bad"):
        cv.create_oval(x - 6, cy - 12, x + PHONE_W + 6, cy + h + 12, outline=MARK, width=3)
    if kind == "new":
        cv.create_rectangle(x + PHONE_W - 52, cy - 9, x + PHONE_W - 8, cy + 7, fill="#0A0A0A", outline="")
        cv.create_text(x + PHONE_W - 30, cy - 1, text="NEW", fill="#FFFFFF", font=(FONT, 8, "bold"))
    if kind == "bad":
        cv.create_text(x + PHONE_W / 2, cy + h + 9, text="too low – most visitors never get here",
                       fill=C["bad"], font=(FONT, 8, "italic"))


def render_rows(cv, x, y, rows, border):
    h = sum(r[1] + 10 for r in rows) + 24
    phone_frame(cv, x, y, h, border)
    cy = y + 12
    for label, rh, kind in rows:
        block(cv, x, cy, rh, label, kind)
        cy += rh + 10 + (12 if kind == "bad" else 0)
    return h


def rows_for(layout, check_id, zone, mode, after, new_kind="new"):
    rows = []
    for key, label, h in layout:
        if key == "reviews_bottom" and not (mode == "move" and not after):
            continue
        if key == "reviews_top" and check_id not in ("reviews_present", "reviews_position",
                                                      "review_volume", "rating_credible"):
            rows.append((label, h, "normal"))
            continue
        if key == zone:
            if mode == "move":
                if after:
                    rows.append((VISUAL_LABEL.get(check_id, label), h, new_kind))
                continue
            if after:
                rows.append((VISUAL_LABEL.get(check_id, label), h, new_kind))
            continue                      # "Now": the element simply isn't there
        if key == "reviews_bottom":
            rows.append((VISUAL_LABEL.get(check_id, label), h, "bad"))
            continue
        rows.append((label, h, "atc" if key == "atc" else "normal"))
    return rows


def render_speed(cv, x, y, layout, after, detail, new_kind="new"):
    rows = [(label, h, "atc" if k == "atc" else "normal") for k, label, h in layout
            if k != "reviews_bottom"]
    h = sum(r[1] + 10 for r in rows) + 24
    phone_frame(cv, x, y, h, C["navy"])
    cy = y + 12
    if after:
        for n, (label, rh, kind) in enumerate(rows):
            if n == 0:
                block(cv, x, cy, rh, "✓ Whole page loads fast", new_kind)
            else:
                block(cv, x, cy, rh, label, kind)
            cy += rh + 10
    else:
        # only the top of the page has loaded; the rest is blank while scripts load
        for label, rh, kind in rows[:2]:
            block(cv, x, cy, rh, label, kind)
            cy += rh + 10
        for i in range(10):
            yy = cy + 8 + i * 16
            cv.create_rectangle(x + 20, yy, x + 20 + (60 + (i * 37) % 140), yy + 8,
                                fill="#E2E8F0", outline="")
        cv.create_text(x + PHONE_W / 2, cy + 200, text="⏳ Still loading…", fill=C["bad"],
                       font=(FONT, 12, "bold"))
        cv.create_oval(x + 8, cy + 150, x + PHONE_W - 8, cy + 250, outline=MARK, width=3)
        cv.create_text(x + PHONE_W / 2, cy + 222, text=detail or "too many scripts",
                       fill=C["bad"], font=(FONT, 9))
    return h


def show_visual(parent, r):
    c = CHECKS[r["id"]]
    top = tk.Toplevel(parent)
    top.title(f"Visual – {c['title']}")
    top.configure(bg=C["bg"])
    layout = HOME_LAYOUT if r["page"] == "Homepage" else PRODUCT_LAYOUT
    zone, mode = c["zone"], c["mode"]
    keys = [k for k, _, _ in layout]
    if zone != "page" and zone not in keys:
        zone = "trust"

    cv = tk.Canvas(top, width=700, height=900, bg=C["bg"], highlightthickness=0)
    cv.pack(padx=16, pady=16)
    left_x, right_x, y0 = 40, 420, 64

    if r.get("chart"):
        h = draw_chart(cv, r)
        tip = (f"Idea: {c['change']}." if not r["passed"] else "This looks healthy in your data.")
        cv.create_text(350, h + 20, text=tip, font=(FONT, 11), fill=C["text"], width=640)
        cv.config(height=h + 50)
        top.transient(parent)
        center(top)
        return

    if r["passed"]:
        cv.create_text(350, 22, text="Already in place ✓", font=(FONT, 14, "bold"), fill=C["ok"])
        if zone == "page":
            h = render_speed(cv, 230, y0, layout, True, r.get("detail"), "have")
        else:
            h = render_rows(cv, 230, y0, rows_for(layout, r["id"], zone, mode, True, "have"),
                            C["navy"])
        tip = "This page already does this well. No change needed."
    else:
        cv.create_text(left_x + PHONE_W / 2, 22, text="Now", font=(FONT, 14, "bold"),
                       fill=C["muted"])
        cv.create_text(right_x + PHONE_W / 2, 22, text="Suggested", font=(FONT, 14, "bold"),
                       fill=C["text"])
        if zone == "page":
            h1 = render_speed(cv, left_x, y0, layout, False, r.get("detail"))
            h2 = render_speed(cv, right_x, y0, layout, True, r.get("detail"))
            tip = f"Circled: the page is still loading. Make it lighter: {c['change']}."
        else:
            h1 = render_rows(cv, left_x, y0, rows_for(layout, r["id"], zone, mode, False), C["navy"])
            h2 = render_rows(cv, right_x, y0, rows_for(layout, r["id"], zone, mode, True), C["navy"])
            tip = ("Circled: move it up, right below the product." if mode == "move"
                   else f"Circled: add this – {c['change']}.")
        h = max(h1, h2)
        cv.create_text(350, y0 + h / 2, text="➜", font=(FONT, 30, "bold"), fill=C["accent"])
    cv.create_text(350, y0 + h + 40, text=tip, font=(FONT, 11), fill=C["text"], width=640)
    cv.config(height=y0 + h + 70)
    top.transient(parent)
    center(top)




# ================================================================ BRIEF, A/B TOOLS, REPORT

ZONE_NAMES = {"atc": "next to the add-to-cart button", "reviews_top": "under the product title",
              "shipping": "under the buy buttons", "trust": "under the buy buttons / below the hero",
              "bundles": "near the buy buttons", "recs": "below the product description",
              "hero": "in the product media gallery", "page": "whole page / theme",
              "description": "product description", "variants": "variant picker",
              "price": "next to the price", "collections": "homepage, high up",
              "chart": "see data finding"}


def make_brief(r, url, sources):
    c = CHECKS[r["id"]]
    sc, im, co, ea = r.get("ice") or ice_score(r["id"], len(sources))   # sources = evidence items
    L = [f"# Brief: {c['title']}", "",
         f"Store: {url}", f"Page: {r['page']}", f"Priority (ICE): {sc:.1f}/10 "
         f"(impact {im}, confidence {co}, ease {ea})", "",
         "## Problem", f"We observed {r['observation']}.", "",
         "## Why it matters", c["why"], "",
         "## Evidence"] + ([f"- {evidence_line(s)}" for s in sources] or ["- (none linked)"]) + [
         "",
         "## Hypothesis", hypothesis(r), "",
         "## Proposed change", f"{c['change'][0].upper()}{c['change'][1:]}.",
         f"Where: {ZONE_NAMES.get(c['zone'], c['zone'])}.", "",
         "## For UX", "- Design the variant on mobile first, then desktop.",
         "- Change only this element so the test result is clear.", "",
         "## For development"] + [f"- {x}" for x in c["fix"]] + (
        ["", "Starter code:", "```", c["code"], "```"] if c.get("code") else []) + [
         "",
         "## QA checklist",
         "- Works on mobile and desktop, in Chrome and Safari",
         "- Correct products, prices and offers shown",
         "- Buttons, links and forms work",
         "- No visible flicker or slower page load",
         "- Visitors are split correctly and the metrics are recorded", "",
         "## Measurement",
         f"- Primary metric: {c['metric']}",
         "- Also watch: conversion rate, average order value, revenue per visitor",
         "- Split: 50/50 · run at least two full weeks · aim for 95% significance", ""]
    return "\n".join(L)


def norm_ppf(p):
    """Inverse normal CDF (Acklam's approximation)."""
    import math
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    if p < 0.02425:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > 1 - 0.02425:
        return -norm_ppf(1 - p)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def sample_size(base_cr, rel_uplift, alpha=0.05, power=0.8):
    import math
    p1 = base_cr
    p2 = base_cr * (1 + rel_uplift)
    za = norm_ppf(1 - alpha / 2)
    zb = norm_ppf(power)
    n = ((za + zb) ** 2) * (p1 * (1 - p1) + p2 * (1 - p2)) / ((p2 - p1) ** 2)
    return math.ceil(n)


def ab_result(va, ca, vb, cb):
    import math
    pa, pb = ca / va, cb / vb
    p = (ca + cb) / (va + vb)
    se = math.sqrt(p * (1 - p) * (1 / va + 1 / vb))
    z = (pb - pa) / se if se > 0 else 0.0
    pval = math.erfc(abs(z) / math.sqrt(2))
    return pa, pb, (pb - pa) / pa if pa > 0 else 0.0, pval


class ABTools(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.title("A/B test tools")
        self.configure(bg=C["bg"])
        ttk.Label(self, text="A/B test tools", font=(FONT, 15, "bold")).pack(anchor="w", padx=20, pady=(18, 0))
        ttk.Label(self, text="Plan how long a test must run, then check if the result is real.",
                  style="Muted.TLabel").pack(anchor="w", padx=20, pady=(2, 10))
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.plan_tab(nb)
        self.result_tab(nb)
        self.transient(app)
        center(self, 720, 700)

    def field(self, f, row, label, default, hint=""):
        ttk.Label(f, text=label).grid(row=row, column=0, sticky="w", pady=7, padx=(0, 14))
        v = tk.StringVar(value=default)
        ttk.Entry(f, textvariable=v, width=14).grid(row=row, column=1, sticky="w")
        if hint:
            ttk.Label(f, text=hint, style="Muted.TLabel").grid(row=row, column=2, sticky="w", padx=10)
        return v

    def out_box(self, f, row):
        t = styled_text(f, height=8)
        t.grid(row=row, column=0, columnspan=3, sticky="nsew", pady=(14, 0))
        f.rowconfigure(row, weight=1)
        f.columnconfigure(2, weight=1)
        return t

    def write(self, t, parts):
        t.config(state="normal")
        t.delete("1.0", "end")
        for text, tag in parts:
            t.insert("end", text, tag)
        t.config(state="disabled")

    def plan_tab(self, nb):
        f = ttk.Frame(nb, padding=18)
        nb.add(f, text="  Plan a test  ")
        wv = self.field(f, 0, "Weekly visitors to the page", "5000")
        cr = self.field(f, 1, "Current conversion rate (%)", "2.0")
        up = self.field(f, 2, "Smallest uplift worth finding (%)", "10", "relative, e.g. 10 = 2.0% → 2.2%")
        out = self.out_box(f, 4)

        def run():
            try:
                weekly, base, lift = float(wv.get()), float(cr.get()) / 100, float(up.get()) / 100
                n = sample_size(base, lift)
                weeks = max(2.0, 2 * n / weekly)
                self.write(out, [("Visitors needed\n", "h2"),
                                 (f"{n:,} per version  ·  {2 * n:,} in total\n", ""),
                                 ("Expected duration\n", "h2"),
                                 (f"about {weeks:.1f} weeks with a 50/50 split\n", ""),
                                 ("\nBased on 95% significance and 80% power. Always run at least two "
                                  "full weeks so every weekday is included. If the duration is very "
                                  "long, test a bigger change or a busier page.", "muted")])
            except (ValueError, ZeroDivisionError):
                self.write(out, [("Please enter numbers in every field.", "bad")])
        ttk.Button(f, text="Calculate", style="Accent.TButton", command=run).grid(
            row=3, column=0, sticky="w", pady=(10, 0))

    def result_tab(self, nb):
        f = ttk.Frame(nb, padding=18)
        nb.add(f, text="  Read results  ")
        va = self.field(f, 0, "A (original) – visitors", "4000")
        ca = self.field(f, 1, "A – purchases", "80")
        vb = self.field(f, 2, "B (variant) – visitors", "4000")
        cb = self.field(f, 3, "B – purchases", "104")
        out = self.out_box(f, 5)

        def run():
            try:
                a_v, a_c, b_v, b_c = (float(x.get()) for x in (va, ca, vb, cb))
                pa, pb, lift, p = ab_result(a_v, a_c, b_v, b_c)
                conf = (1 - p) * 100
                if p < 0.05 and lift > 0:
                    verdict, tag = "B wins. The difference is very likely real.", "ok"
                elif p < 0.05 and lift < 0:
                    verdict, tag = "B loses. Keep the original.", "bad"
                else:
                    verdict, tag = ("No clear winner yet. Keep the test running or accept that "
                                    "the change makes little difference."), "bad"
                self.write(out, [("Conversion rate\n", "h2"),
                                 (f"A: {pa * 100:.2f}%    B: {pb * 100:.2f}%    "
                                  f"Change: {lift * 100:+.1f}%\n", ""),
                                 ("Confidence\n", "h2"), (f"{conf:.1f}%  (p = {p:.3f})\n", ""),
                                 ("Verdict\n", "h2"), (verdict + "\n", tag),
                                 ("\nTwo-sided test at 95%. Also compare revenue per visitor: a "
                                  "change can raise conversion but lower order value.", "muted")])
            except (ValueError, ZeroDivisionError):
                self.write(out, [("Please enter numbers in every field (visitors above 0).", "bad")])
        ttk.Button(f, text="Check result", style="Accent.TButton", command=run).grid(
            row=4, column=0, sticky="w", pady=(10, 0))


def html_report(app):
    import html as H
    rows = sorted(app.results, key=lambda r: (r["passed"], -r.get("ice", (0,))[0]))
    bad = [r for r in rows if not r["passed"]]
    out = ["<!doctype html><html><head><meta charset='utf-8'><title>CRO report</title>",
           "<meta name='viewport' content='width=device-width, initial-scale=1'><style>",
           "body{font-family:Segoe UI,Helvetica,Arial,sans-serif;color:#0a0a0a;background:#fff;"
           "max-width:860px;margin:40px auto;padding:0 20px;line-height:1.55}",
           "h1{font-size:28px;margin:0}h2{font-size:18px;margin:36px 0 8px;border-bottom:2px solid #0a0a0a;padding-bottom:6px}",
           ".muted{color:#737373;font-size:14px}.card{border:1px solid #e5e5e5;padding:16px 18px;margin:12px 0}",
           ".score{display:inline-block;background:#0a0a0a;color:#fff;font-weight:700;padding:2px 8px;margin-right:8px}",
           "table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid #e5e5e5;padding:8px;text-align:left}",
           ".ev{font-size:13px;color:#404040;margin:4px 0 0 0}</style></head><body>",
           f"<h1>Shopify CRO report</h1><p class='muted'>{H.escape(app.url)}</p>",
           f"<p><b>{len(rows) - len(bad)} of {len(rows)}</b> checks passed · <b>{len(bad)}</b> ideas to test</p>",
           "<h2>Ideas to test, by priority</h2>"]
    for r in bad:
        c = CHECKS[r["id"]]
        out.append(f"<div class='card'><span class='score'>{r['ice'][0]:.1f}</span><b>{H.escape(c['title'])}</b>"
                   f" <span class='muted'>· {H.escape(r['page'])}</span>"
                   f"<p>{H.escape(hypothesis(r))}</p>")
        for s_ in app.evidence_for(r["id"]):
            out.append(f"<p class='ev'>Evidence – {H.escape(evidence_line(s_))}</p>")
        out.append("</div>")
    if getattr(app, "audit", None) and Path(app.audit["shot"]).exists():
        import base64
        data = base64.b64encode(Path(app.audit["shot"]).read_bytes()).decode()
        out.append("<h2>Visual audit (real mobile page)</h2>"
                   "<p class='muted'>Dashed line: end of the first phone screen. Red circles: what "
                   "should change.</p><div style='display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start'>"
                   f"<img src='data:image/png;base64,{data}' style='width:300px;border:1px solid #e5e5e5'>"
                   "<ol style='flex:1;min-width:240px;padding-left:18px'>")
        for it in app.audit["legend"]:
            if it["n"]:
                w = "<b style='color:#DC2626'>" if it["bad"] else ""
                we = "</b>" if it["bad"] else ""
                out.append(f"<li value='{it['n']}'>{w}{H.escape(it['label'])}: {H.escape(it['status'])}{we}</li>")
        missing = [it for it in app.audit["legend"] if not it["n"]]
        out.append("</ol></div>")
        if missing:
            out.append("<p class='muted'>Not found: " + ", ".join(H.escape(m["label"]) for m in missing) + "</p>")
    out.append("<h2>All checks</h2><table><tr><th>Check</th><th>Page</th><th>Result</th></tr>")
    for r in rows:
        out.append(f"<tr><td>{H.escape(CHECKS[r['id']]['title'])}</td><td>{H.escape(r['page'])}</td>"
                   f"<td>{'OK' if r['passed'] else '<b>Fix</b>'}</td></tr>")
    out.append("</table>")
    if app.notes:
        out.append("<h2>Notes</h2>" + "".join(f"<p class='muted'>{H.escape(n)}</p>" for n in app.notes))
    out.append("<p class='muted' style='margin-top:40px'>ICE = impact, confidence, ease (1–10). "
               "Results are ideas to test, not guarantees.</p></body></html>")
    return "\n".join(out)


# ================================================================ GUI HELPERS

def center(win, w=None, h=None, lock=True):
    win.update_idletasks()
    w = w or win.winfo_width()
    h = h or win.winfo_height()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    w, h = min(w, sw - 40), min(h, sh - 80)
    if lock:  # dialogs keep their size floor, so buttons never get squeezed out
        win.minsize(min(w, int(w * 0.85)), min(h, int(h * 0.85)))
    win.geometry(f"{w}x{h}+{max((sw - w) // 2, 0)}+{max((sh - h) // 3, 0)}")


def scroll_text(parent, **kw):
    """A Text with a scrollbar that is always visible, so it is clear when text continues.
    pack/grid/place on the returned Text lay out its frame (text + scrollbar) together."""
    box = tk.Frame(parent, bg=kw.get("bg", C["card"]))
    t = tk.Text(box, **kw)
    sb = ttk.Scrollbar(box, orient="vertical", command=t.yview)
    t.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    t.pack(side="left", fill="both", expand=True)
    for name in ("pack", "grid", "place", "pack_forget", "grid_forget", "grid_remove"):
        setattr(t, name, getattr(box, name))
    t.box = box
    return t


class ScrollFrame(ttk.Frame):
    """A frame whose content scrolls. The scrollbar appears as soon as content is taller
    than the space, so nothing is ever cut off silently. Put widgets in .inner."""

    def __init__(self, parent, bg=None, **kw):
        super().__init__(parent, **kw)
        self.cv = tk.Canvas(self, highlightthickness=0, bd=0, bg=bg or C["bg"])
        self.sb = ttk.Scrollbar(self, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=self.sb.set)
        self.cv.pack(side="left", fill="both", expand=True)
        self.inner = ttk.Frame(self.cv)
        self._win = self.cv.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self._update())
        self.cv.bind("<Configure>", lambda e: (self.cv.itemconfigure(self._win, width=e.width),
                                              self._update()))
        for w in (self.cv, self.inner):
            w.bind("<Enter>", lambda e: self.cv.bind_all("<MouseWheel>", self._wheel))
            w.bind("<Leave>", lambda e: self.cv.unbind_all("<MouseWheel>"))

    def _update(self):
        self.cv.configure(scrollregion=self.cv.bbox("all"))
        need = self.inner.winfo_reqheight() > self.cv.winfo_height() + 1
        if need and not self.sb.winfo_ismapped():
            self.sb.pack(side="right", fill="y", before=self.cv)
        elif not need and self.sb.winfo_ismapped():
            self.sb.pack_forget()
            self.cv.yview_moveto(0)

    def _wheel(self, e):
        if self.sb.winfo_ismapped():
            self.cv.yview_scroll(int(-e.delta / 120) or (-1 if e.delta > 0 else 1), "units")


def styled_text(parent, height=10):
    t = scroll_text(parent, wrap="word", height=height, font=(FONT, 11), bg=C["card"], fg=C["text"],
                    relief="flat", padx=16, pady=14, highlightthickness=1,
                    highlightbackground=C["line"], highlightcolor=C["line"], spacing2=2)
    t.tag_config("h1", font=(FONT, 15, "bold"), spacing3=6)
    t.tag_config("h2", font=(FONT, 11, "bold"), foreground=C["navy2"], spacing1=12, spacing3=4)
    t.tag_config("muted", foreground=C["muted"], font=(FONT, 10))
    t.tag_config("ok", foreground=C["ok"], font=(FONT, 11, "bold"))
    t.tag_config("bad", foreground=C["bad"], font=(FONT, 11, "bold"))
    t.tag_config("mark", foreground=MARK, font=(FONT, 11, "bold"))
    t.tag_config("code", font=("Consolas", 10), background="#F3F3F3", lmargin1=10, lmargin2=10)
    t.tag_config("ev", foreground=C["navy2"], font=(FONT, 10), lmargin1=14, lmargin2=26, spacing3=6)
    t.tag_config("step", lmargin1=0, lmargin2=24, spacing3=6)
    t.tag_config("evbad", foreground=MARK, font=(FONT, 10), lmargin1=14, lmargin2=26, spacing3=6)
    return t


def open_location(loc):
    if not loc:
        return
    if loc.startswith("http"):
        webbrowser.open(loc)
    elif os.path.exists(loc):
        if sys.platform.startswith("win"):
            os.startfile(loc)  # type: ignore[attr-defined]
        else:
            webbrowser.open(Path(loc).as_uri())
    else:
        messagebox.showwarning(APP_NAME, f"Can't open:\n{loc}")


# ================================================================ MAIN APP

class Tooltip:
    """Small hover hint for a widget."""

    def __init__(self, widget, text, delay=450):
        self.widget, self.text, self.delay = widget, text, delay
        self.tip, self.job = None, None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _=None):
        self._cancel()
        self.job = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None

    def _show(self):
        if self.tip:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, bg="#0A0A0A", fg="#FFFFFF", font=(FONT, 9),
                 padx=10, pady=6, justify="left", wraplength=320).pack()

    def _hide(self, _=None):
        self._cancel()
        if self.tip:
            self.tip.destroy()
            self.tip = None


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.configure(bg=C["bg"])
        self.sources = load_sources()
        self.results, self.notes, self.url = [], [], ""
        self.audit = None
        self._style()
        self._build()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        min_w = min(self._min_width(), sw - 40)
        min_h = min(640, sh - 80)
        w = max(min_w, min(1320, int(sw * 0.88)))
        h = max(min_h, min(860, int(sh * 0.86)))
        self.minsize(min_w, min_h)
        center(self, w, h, lock=False)
        self.report_callback_exception = self._on_error

    def _on_error(self, exc, val, tb):
        import traceback
        details = "".join(traceback.format_exception(exc, val, tb))[-1500:]
        messagebox.showerror(APP_NAME, f"Something went wrong:\n\n{val}\n\nDetails:\n{details}")

    def _style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure(".", font=(FONT, 11), background=C["bg"], foreground=C["text"])
        s.configure("TFrame", background=C["bg"])
        s.configure("TLabel", background=C["bg"])
        s.configure("Muted.TLabel", background=C["bg"], foreground=C["muted"], font=(FONT, 10))
        s.configure("Accent.TButton", font=(FONT, 11, "bold"), foreground="#FFFFFF",
                    background=C["accent"], borderwidth=0, padding=(18, 9))
        s.map("Accent.TButton", background=[("active", C["accent_dark"]), ("disabled", "#D4D4D4")],
              foreground=[("disabled", "#F8FAFC")])
        s.configure("Ghost.TButton", font=(FONT, 10), background=C["card"], foreground=C["text"],
                    borderwidth=1, padding=(12, 7))
        s.map("Ghost.TButton", background=[("active", "#F0F0F0")],
              foreground=[("disabled", "#B5B5B5")])
        s.configure("Header.TButton", font=(FONT, 10, "bold"), background=C["navy2"],
                    foreground="#FFFFFF", borderwidth=0, padding=(14, 7))
        s.map("Header.TButton", background=[("active", "#404040")])
        s.configure("Treeview", font=(FONT, 11), rowheight=34, background=C["card"],
                    fieldbackground=C["card"], borderwidth=0)
        s.configure("Treeview.Heading", font=(FONT, 10, "bold"), background="#F0F0F0",
                    foreground=C["navy2"], borderwidth=0, padding=(8, 6))
        s.map("Treeview", background=[("selected", "#E5E5E5")], foreground=[("selected", C["text"])])
        s.configure("TCheckbutton", background=C["bg"], font=(FONT, 10))
        s.configure("TEntry", padding=8, fieldbackground="#FFFFFF", bordercolor="#D4D4D4",
                    lightcolor="#D4D4D4", darkcolor="#D4D4D4")
        s.map("TEntry", bordercolor=[("focus", "#0A0A0A")], lightcolor=[("focus", "#0A0A0A")],
              darkcolor=[("focus", "#0A0A0A")])
        s.configure("TCombobox", fieldbackground="#FFFFFF", bordercolor="#D4D4D4",
                    arrowcolor="#0A0A0A", background="#FFFFFF")
        s.map("TCombobox", fieldbackground=[("readonly", "#FFFFFF")],
              selectbackground=[("readonly", "#FFFFFF")],
              selectforeground=[("readonly", "#0A0A0A")],
              background=[("readonly", "#FFFFFF")])
        s.configure("TNotebook", background=C["bg"], borderwidth=0)
        s.configure("TNotebook.Tab", background="#EDEDED", foreground=C["text"], padding=(16, 7),
                    borderwidth=0, font=(FONT, 10, "bold"))
        s.map("TNotebook.Tab", background=[("selected", "#FFFFFF")],
              foreground=[("selected", C["text"])])
        s.configure("TCheckbutton", indicatorbackground="#FFFFFF", indicatorforeground="#0A0A0A")
        s.configure("Mono.Horizontal.TProgressbar", troughcolor="#EDEDED", background="#0A0A0A",
                    bordercolor="#EDEDED", lightcolor="#0A0A0A", darkcolor="#0A0A0A", thickness=4)
        s.configure("Filter.TRadiobutton", font=(FONT, 10), background=C["bg"], padding=(10, 5),
                    indicatoron=False)
        s.configure("Toolbutton", font=(FONT, 10), background="#EDEDED", foreground=C["text"],
                    padding=(12, 5), borderwidth=0)
        s.map("Toolbutton", background=[("selected", "#0A0A0A"), ("active", "#D4D4D4")],
              foreground=[("selected", "#FFFFFF")])
        s.configure("Vertical.TScrollbar", background="#D4D4D4", troughcolor="#F5F5F5",
                    bordercolor="#F5F5F5", arrowcolor="#0A0A0A", lightcolor="#D4D4D4",
                    darkcolor="#D4D4D4")
        s.map("Vertical.TScrollbar", background=[("active", "#A3A3A3")])

    def _build(self):
        header = tk.Frame(self, bg=C["navy"])
        header.pack(fill="x")
        header.columnconfigure(1, weight=1)
        self.header = header
        brand = tk.Frame(header, bg=C["navy"])
        brand.grid(row=0, column=0, sticky="w", padx=(22, 0), pady=14)
        tk.Label(brand, text="■", fg="#FFFFFF", bg=C["navy"], font=(FONT, 14)).pack(side="left", padx=(0, 6))
        tk.Label(brand, text=APP_NAME, fg="#FFFFFF", bg=C["navy"],
                 font=(FONT, 16, "bold")).pack(side="left")
        self.brand = brand
        self.tag_font = tkfont.Font(family=FONT, size=11)
        self.tagline = tk.Label(header, text="find what stops shoppers from buying", fg="#A3A3A3",
                                bg=C["navy"], font=self.tag_font, anchor="w", justify="left")
        self.tagline.grid(row=0, column=1, sticky="w", padx=(16, 12))
        hb = tk.Frame(header, bg=C["navy"])
        self.header_btns = hb
        for text, cmd, hint in [
                ("A/B test tools", lambda: ABTools(self),
                 "Plan how long a test must run, or check whether a test result is real."),
                ("Sources", lambda: SourcesWindow(self),
                 "The research and case studies behind each check, and the rule each check uses."),
                ("AI add-on", lambda: AISettingsWindow(self),
                 "Optional: let an AI read the research you add. Choose Claude, Gemini or a free "
                 "local model, and enter your own key."),
                ("?  Help & FAQ", lambda: HelpWindow(self),
                 "How it works, common questions, explanations of terms and contact.")]:
            b = ttk.Button(hb, text=text, style="Header.TButton", command=cmd)
            b.pack(side="left", padx=(6, 0))
            Tooltip(b, hint)
        hb.grid(row=0, column=2, sticky="e", padx=(0, 22), pady=12)
        header.bind("<Configure>", lambda e: self._layout_header())

        bar = ttk.Frame(self, padding=(22, 18, 22, 8))
        bar.pack(fill="x")
        lbl = ttk.Frame(bar)
        lbl.pack(fill="x")
        ttk.Label(lbl, text="Store or product link", font=(FONT, 11, "bold")).pack(side="left")
        ttk.Label(lbl, text="   or upload your analytics data", style="Muted.TLabel").pack(side="left")
        row = ttk.Frame(bar)
        row.pack(fill="x", pady=(6, 4))
        self.url_var = tk.StringVar()
        b_clear = ttk.Button(row, text="Clear", style="Ghost.TButton", command=self.clear)
        b_clear.pack(side="right", padx=(8, 0))
        Tooltip(b_clear, "Remove all results and start again.")
        b_csv = ttk.Button(row, text="Upload CSV", style="Ghost.TButton", command=self.upload_data)
        b_csv.pack(side="right", padx=(8, 0))
        Tooltip(b_csv, "Upload a Google Analytics 4 or Shopify Analytics export (CSV) to find weak "
                       "spots in your data: devices, channels, landing pages, cart and checkout.")
        self.btn = ttk.Button(row, text="Analyze", style="Accent.TButton", command=self.start)
        self.btn.pack(side="right", padx=(10, 0))
        Tooltip(self.btn, "Check the store's homepage and a product page.")
        entry = ttk.Entry(row, textvariable=self.url_var, font=(FONT, 12), width=10)
        entry.pack(side="left", fill="x", expand=True, ipady=4)
        entry.bind("<Return>", lambda e: self.start())
        entry.focus_set()
        self.progress = ttk.Progressbar(bar, mode="indeterminate", style="Mono.Horizontal.TProgressbar")
        opt = ttk.Frame(bar)
        opt.pack(fill="x")
        self.opt_frame = opt
        opt.columnconfigure(1, weight=1)
        self.speed_var = tk.BooleanVar(value=True)
        checks_row = ttk.Frame(opt)
        checks_row.grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(checks_row, text="Google mobile speed test (optional)",
                        variable=self.speed_var).pack(side="left")
        self.browser_var = tk.BooleanVar(value=browser_available())
        ttk.Checkbutton(checks_row, text="Real browser audit (optional, recommended)",
                        variable=self.browser_var, command=self._browser_toggled).pack(
            side="left", padx=(18, 0))
        self.status = ttk.Label(opt, text="Example: allbirds.com  or a link containing /products/",
                                style="Muted.TLabel", anchor="e", justify="right")
        self.status.grid(row=0, column=1, sticky="e", padx=(12, 0))
        self.why_opt = ttk.Label(
            opt, style="Muted.TLabel", justify="left",
            text="Why optional? They take longer: speed test up to 1 min, browser audit 20–40 s "
                 "(opens the page as a phone in Chrome/Edge; more accurate, with a marked screenshot).")
        self.why_opt.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.status.config(wraplength=520)
        self.why_opt.config(wraplength=1100)

        body = ttk.Frame(self, padding=(22, 8, 22, 22))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=6, uniform="c")
        body.columnconfigure(1, weight=6, uniform="c")
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.score = tk.Label(left, text="No analysis yet", bg=C["card"], fg=C["muted"],
                              font=(FONT, 12, "bold"), anchor="w", padx=16, pady=12)
        score_row = tk.Frame(left, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
        score_row.pack(fill="x", pady=(0, 10))
        self.b_save = ttk.Button(score_row, text="Save report", style="Ghost.TButton",
                                 command=self.save_report, state="disabled")
        self.b_save.pack(side="right", padx=10, pady=8)
        Tooltip(self.b_save, "Export the results as a shareable HTML page (or text / JSON).")
        self.score.pack(in_=score_row, side="left", fill="x", expand=True)
        self.score.lift(score_row)            # keep the score text above its card
        frow = ttk.Frame(left)
        frow.pack(fill="x", pady=(0, 8))
        ttk.Label(frow, text="Show", style="Muted.TLabel").pack(side="left", padx=(0, 8))
        self.filter_var = tk.StringVar(value="all")
        self.filter_btns = {}
        for val, label in [("fix", "To fix"), ("all", "All"), ("ok", "OK")]:
            rb = ttk.Radiobutton(frow, text=label, value=val, variable=self.filter_var,
                                 style="Toolbutton", command=self._render_tree)
            rb.pack(side="left", padx=(0, 4))
            self.filter_btns[val] = rb
        ttk.Label(frow, text="Double-click an item for fix steps", style="Muted.TLabel").pack(side="right")
        self.score.bind("<Configure>", lambda e: self.score.config(wraplength=max(e.width - 24, 120),
                                                                   justify="left"))
        tree_wrap = ttk.Frame(left)
        tree_wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tree_wrap, columns=("prio", "status", "page"),
                                 show="tree headings", selectmode="browse")
        self.tree.heading("prio", text="Priority", anchor="w")
        self.tree.column("prio", width=72, anchor="w", stretch=False)
        self.tree.heading("#0", text="Check", anchor="w")
        self.tree.heading("status", text="Result", anchor="w")
        self.tree.heading("page", text="Page", anchor="w")
        self.tree.column("#0", width=330, anchor="w")
        self.tree.column("status", width=72, anchor="w", stretch=False)
        self.tree.column("page", width=112, anchor="w", stretch=False)
        self.tree.tag_configure("bad", foreground=C["text"], font=(FONT, 11, "bold"))
        self.tree.tag_configure("ok", foreground=C["muted"])
        sb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.show_detail())
        self.tree.bind("<Double-1>", lambda e: self.fix() if self.tree.selection() else None)
        self.tree.bind("<Configure>", lambda e: self.tree.configure(
            displaycolumns=("prio", "status", "page") if e.width >= 520 else ("prio", "status")))

        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="nsew")
        actions = ttk.Frame(right, padding=(0, 10, 0, 0))
        actions.pack(side="bottom", fill="x")
        self.actions = actions
        self.b_visual = ttk.Button(actions, text="Open visual audit", style="Ghost.TButton",
                                   command=self.visual, state="disabled")
        self.b_brief = ttk.Button(actions, text="Create UX/dev brief", style="Ghost.TButton",
                                  command=self.brief, state="disabled")
        self.b_fix = ttk.Button(actions, text="Help me fix this", style="Accent.TButton",
                                command=self.fix, state="disabled")
        Tooltip(self.b_visual, "See it on the page: a marked screenshot (real browser audit), "
                               "a before/after sketch, or a chart for data findings.")
        Tooltip(self.b_brief, "A ready-to-share brief for designers and developers: problem, idea, "
                              "build steps, QA checklist and how to measure it.")
        Tooltip(self.b_fix, "Step-by-step instructions, code you can paste and a ready-made AI prompt.")
        actions.columnconfigure(1, weight=1)
        self.b_visual.grid(row=0, column=0, sticky="w")
        self.b_brief.grid(row=0, column=2, sticky="e", padx=(0, 8))
        self.b_fix.grid(row=0, column=3, sticky="e")
        self.detail = styled_text(right)
        self.detail.pack(side="top", fill="both", expand=True)
        self._welcome()

    def _layout_header(self):
        """Buttons stay where they are; only the tagline font shrinks or grows to fit."""
        w = self.header.winfo_width()
        if w <= 1:
            return
        avail = w - self.brand.winfo_reqwidth() - self.header_btns.winfo_reqwidth() - 80
        text = self.tagline.cget("text")
        size = 8
        for candidate in range(12, 7, -1):
            self.tag_font.configure(size=candidate)
            if self.tag_font.measure(text) <= avail:
                size = candidate
                break
        self.tag_font.configure(size=size)

    def _min_width(self):
        self.update_idletasks()
        self.tag_font.configure(size=8)
        header = (self.brand.winfo_reqwidth() + self.header_btns.winfo_reqwidth()
                  + self.tag_font.measure(self.tagline.cget("text")) + 110)
        actions = sum(b.winfo_reqwidth() for b in (self.b_visual, self.b_brief, self.b_fix)) + 24
        body = 2 * (actions + 20) + 60
        return max(header, body, 1180)

    def _welcome(self):
        t = self.detail
        t.config(state="normal")
        t.delete("1.0", "end")
        t.insert("end", "How it works\n", "h1")
        steps = ["Paste a store or product link and press Analyze, or upload your analytics (CSV).",
                 "Click an item to see what was found, why it matters and how it was checked.",
                 "If you like, you can open its visual audit, get step-by-step fixes or create a "
                 "UX/dev brief.",
                 "Filter with To fix / All / OK. 'Save report' shares the results.",
                 "Ideas are ranked by ICE priority. A/B test tools, Sources, AI add-on and Help are at the top."]
        for i, s_ in enumerate(steps, 1):
            t.insert("end", f"{i}.  {s_}\n", "step")
        t.insert("end", "New to CRO? See '? Help & FAQ'. Results are ideas to test, not guarantees.",
                 "muted")
        t.config(state="disabled")

    # ---------- analysis
    def start(self):
        url = self.url_var.get().strip()
        if not url:
            return
        self.url = normalize(url)
        self.btn.config(state="disabled")
        self.status.config(text="Starting…")
        self.score.config(text="Analyzing…", fg=C["muted"])
        self.progress.pack(fill="x", pady=(6, 0), before=self.opt_frame)
        self.progress.start(12)
        use_browser = self.browser_var.get() and browser_available()
        threading.Thread(target=self._work, args=(url, self.speed_var.get(), use_browser),
                         daemon=True).start()

    def _work(self, url, speed, use_browser=False):
        try:
            res, notes, audit = analyze(url, speed,
                                        lambda m: self.after(0, lambda: self.status.config(text=m)),
                                        with_browser=use_browser)
            self.after(0, self._done, res, notes, True, audit)
        except Exception as e:
            self.after(0, self._fail, str(e))

    def _fail(self, msg):
        self._stop_progress()
        self.btn.config(state="normal")
        self.status.config(text="Something went wrong.")
        self.score.config(text="Analysis failed", fg=C["bad"])
        messagebox.showerror(APP_NAME, msg)

    def _stop_progress(self):
        try:
            self.progress.stop()
            self.progress.pack_forget()
        except Exception:
            pass

    def _done(self, results, notes, replace_site=True, audit=None):
        self._stop_progress()
        self.btn.config(state="normal")
        if replace_site:
            self.audit = audit
        if replace_site:   # new website check: keep uploaded-data findings, replace site ones
            keep = [r for r in self.results if r["page"] == "Your data"]
            old_notes = [n for n in self.notes if n.startswith("Analytics file")]
        else:              # new data upload: keep everything already on screen
            keep = list(self.results)
            old_notes = list(self.notes)
        results = keep + results
        notes = old_notes + notes
        self.results, self.notes = results, notes
        passed = sum(r["passed"] for r in results)
        total = len(results)
        issues = total - passed
        self.score.config(text=f"{passed} of {total} checks passed   ·   {issues} idea(s) to test",
                          fg=C["ok"] if issues == 0 else C["text"])
        self.status.config(text="Done. Click an item to see details.")
        for r in results:
            r["ice"] = ice_score(r["id"], evidence_score(self.sources, r["id"]))
        self.b_save.config(state="normal")
        self._render_tree()
        self._summary()

    def refresh_priorities(self):
        """Sources changed: recompute ICE and redraw, keeping the selected item."""
        sel = self.tree.selection()
        for r in self.results:
            r["ice"] = ice_score(r["id"], evidence_score(self.sources, r["id"]))
        if self.results:
            self._render_tree()
            if sel and self.tree.exists(sel[0]):
                self.tree.selection_set(sel[0])
                self.show_detail()

    def _render_tree(self):
        results = self.results
        self.tree.delete(*self.tree.get_children())
        n_fix = sum(1 for r in results if not r["passed"])
        n_ok = len(results) - n_fix
        self.filter_btns["fix"].config(text=f"To fix ({n_fix})")
        self.filter_btns["all"].config(text=f"All ({len(results)})")
        self.filter_btns["ok"].config(text=f"OK ({n_ok})")
        mode = self.filter_var.get()
        order = sorted(range(len(results)),
                       key=lambda i: (results[i]["passed"], -results[i].get("ice", (0,))[0]))
        for i in order:
            r = results[i]
            if (mode == "fix" and r["passed"]) or (mode == "ok" and not r["passed"]):
                continue
            c = CHECKS[r["id"]]
            name = c["title"] + (f"  ({r['detail']})" if r["detail"] else "")
            self.tree.insert("", "end", iid=str(i), text="  " + name,
                             values=("" if r["passed"] else f"{r['ice'][0]:.1f}",
                                     "✓ OK" if r["passed"] else "✗ Fix", r["page"]),
                             tags=("ok" if r["passed"] else "bad",))

    def _summary(self):
        t = self.detail
        t.config(state="normal")
        t.delete("1.0", "end")
        t.insert("end", "Summary\n", "h1")
        t.insert("end", f"{self.url}\n", "muted")
        bad = sorted([r for r in self.results if not r["passed"]], key=lambda r: -r["ice"][0])
        if bad:
            t.insert("end", "Top ideas to test (by ICE priority)\n", "h2")
            for r in bad[:6]:
                t.insert("end", f"{r['ice'][0]:.1f}   {CHECKS[r['id']]['title']} "
                                f"({r['page'].lower()})\n")
        else:
            t.insert("end", "\nAll checks passed. Nice work.\n", "ok")
        if self.notes:
            t.insert("end", "Notes\n", "h2")
            for n in self.notes:
                t.insert("end", f"•  {n}\n", "muted")
        t.insert("end", "\nClick any item on the left to see the details.", "muted")
        t.config(state="disabled")
        self.b_visual.config(state="normal")
        self.b_fix.config(state="normal")
        self.b_brief.config(state="normal")

    def clear(self):
        self.results, self.notes, self.url = [], [], ""
        self.url_var.set("")
        self.tree.delete(*self.tree.get_children())
        self.score.config(text="No analysis yet", fg=C["muted"])
        self.status.config(text="Cleared. Paste a link or upload analytics data.")
        self.b_visual.config(state="disabled")
        self.b_fix.config(state="disabled")
        self.b_brief.config(state="disabled")
        self.audit = None
        self.b_save.config(state="disabled")
        for val, label in [("fix", "To fix"), ("all", "All"), ("ok", "OK")]:
            self.filter_btns[val].config(text=label)
        self._welcome()

    def upload_data(self):
        if messagebox.askyesno(APP_NAME, "Upload a CSV export from Google Analytics 4 or Shopify "
                                         "Analytics.\n\nDo you want to see how to export it first?"):
            messagebox.showinfo(APP_NAME, EXPORT_HELP)
        path = filedialog.askopenfilename(title="Choose analytics CSV",
                                          filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            res, notes = analyze_data(path)
        except Exception as e:
            messagebox.showerror(APP_NAME, str(e))
            return
        # replace earlier data findings with the same ids, keep site results
        ids = {r["id"] for r in res}
        self.results = [r for r in self.results if not (r["page"] == "Your data" and r["id"] in ids)]
        self.notes = [n for n in self.notes if not n.startswith("Thresholds")]
        if not self.url:
            self.url = "analytics data"
        self._done(res, notes, replace_site=False)
        self.status.config(text=f"Added {len(res)} finding(s) from {Path(path).name}.")

    def selected(self):
        sel = self.tree.selection()
        return self.results[int(sel[0])] if sel else None

    def ensure_selected(self):
        """If nothing is selected, select the first item that needs fixing."""
        r = self.selected()
        if r:
            return r
        if not self.results:
            messagebox.showinfo(APP_NAME, "Run an analysis first, then pick an item on the left.")
            return None
        for iid in self.tree.get_children():
            if not self.results[int(iid)]["passed"]:
                self.tree.selection_set(iid)
                self.tree.see(iid)
                self.update_idletasks()
                self.show_detail()
                return self.results[int(iid)]
        messagebox.showinfo(APP_NAME, "Pick an item on the left first.")
        return None

    def evidence_for(self, check_id):
        return evidence_items(self.sources, check_id)

    def show_detail(self):
        r = self.selected()
        if not r:
            return
        c = CHECKS[r["id"]]
        t = self.detail
        t.config(state="normal")
        t.delete("1.0", "end")
        t.insert("end", c["title"] + "\n", "h1")
        t.insert("end", ("✓  Looks good" if r["passed"] else "✗  Worth fixing") + "\n",
                 "ok" if r["passed"] else "bad")
        t.insert("end", r["page"] + (f"  ·  {r['detail']}" if r["detail"] else "") + "\n", "muted")
        if not r["passed"] and r.get("ice"):
            sc, im, co, ea = r["ice"]
            t.insert("end", f"Priority (ICE) {sc:.1f} / 10   ·   Impact {im} · Confidence {co} · "
                            f"Ease {ea}\n", "muted")
        t.insert("end", "Why it matters\n", "h2")
        t.insert("end", c["why"] + "\n")
        if r["id"] in CHECK_RULES:
            t.insert("end", "How this was checked\n", "h2")
            t.insert("end", CHECK_RULES[r["id"]] + "\n", "muted")
        if not r["passed"]:
            t.insert("end", "What we found\n", "h2")
            t.insert("end", f"We found {r['observation']}.\n")
            t.insert("end", "What to try\n", "h2")
            t.insert("end", f"Try {c['change']}. The goal is to help visitors {c['action']}.\n")
            t.insert("end", "Hypothesis (for an A/B test)\n", "h2")
            t.insert("end", hypothesis(r) + "\n")
        ev = self.evidence_for(r["id"])
        if ev:
            t.insert("end", "Evidence (research and case studies from Sources)\n", "h2")
            for item in ev:
                t.insert("end", f"•  {evidence_line(item)}\n",
                         "evbad" if item["effect"] != "positive" else "ev")
        t.insert("end", ("\nThresholds are rules of thumb for spotting problems, not benchmarks."
                         if r["page"] == "Your data" else
                         "\nOne store's result is a starting point for a hypothesis, not a guarantee."),
                 "muted")
        t.config(state="disabled")
        self.b_visual.config(state="normal")
        self.b_fix.config(state="normal")
        self.b_brief.config(state="normal")

    def brief(self):
        r = self.ensure_selected()
        if not r:
            return
        text = make_brief(r, self.url, self.evidence_for(r["id"]))
        top = tk.Toplevel(self)
        top.title(f"Brief – {CHECKS[r['id']]['title']}")
        top.configure(bg=C["bg"])
        btns = ttk.Frame(top, padding=(20, 0, 20, 20))
        btns.pack(side="bottom", fill="x")
        t = styled_text(top, height=26)
        t.pack(fill="both", expand=True, padx=20, pady=(20, 10))
        for line in text.splitlines():
            if line.startswith("# "):
                t.insert("end", line[2:] + "\n", "h1")
            elif line.startswith("## "):
                t.insert("end", line[3:] + "\n", "h2")
            else:
                t.insert("end", line + "\n")
        t.config(state="disabled")

        def copy():
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo(APP_NAME, "Brief copied. Paste it into Slack, Notion, Jira or an email.",
                                parent=top)

        def save():
            p = filedialog.asksaveasfilename(parent=top, defaultextension=".md",
                                             initialfile=f"brief_{r['id']}.md",
                                             filetypes=[("Markdown", "*.md"), ("Text", "*.txt")])
            if p:
                Path(p).write_text(text, encoding="utf-8")
                messagebox.showinfo(APP_NAME, f"Saved:\n{p}", parent=top)
        ttk.Button(btns, text="Save as file", style="Ghost.TButton", command=save).pack(side="left")
        ttk.Button(btns, text="Copy brief", style="Accent.TButton", command=copy).pack(side="right")
        top.transient(self)
        center(top, 780, 700)

    def visual(self):
        if self.audit and not self.tree.selection():
            AuditWindow(self, self.audit)          # nothing selected: show the whole audit
            return
        r = self.ensure_selected()
        if not r:
            return
        if self.audit and r["page"] == "Product page":
            for key, ids in MARK_CHECKS.items():
                if r["id"] in ids:
                    AuditWindow(self, self.audit, focus=key)
                    return
        show_visual(self, r)

    def open_audit(self):
        if self.audit:
            AuditWindow(self, self.audit)

    def _browser_toggled(self):
        if self.browser_var.get() and not browser_available():
            self.browser_var.set(False)
            if messagebox.askyesno(APP_NAME, "The real browser audit needs one small add-on "
                                   "(Playwright, about 40 MB). It uses the Chrome or Edge already "
                                   "on your computer.\n\nInstall it now?"):
                self.status.config(text="Installing Playwright… this can take a minute.")
                threading.Thread(target=self._install_browser, daemon=True).start()

    def _install_browser(self):
        import subprocess
        flags = 0x08000000 if sys.platform.startswith("win") else 0   # no console window
        exe = sys.executable
        if exe.lower().endswith("pythonw.exe"):
            exe = exe[:-5] + ".exe"
        try:
            r = subprocess.run([exe, "-m", "pip", "install", "playwright"], capture_output=True,
                               text=True, creationflags=flags, timeout=900)
            ok = r.returncode == 0
            msg = "" if ok else (r.stderr or r.stdout)[-600:]
        except Exception as e:
            ok, msg = False, str(e)
        self.after(0, self._install_done, ok, msg)

    def _install_done(self, ok, msg):
        if ok:
            import importlib
            importlib.invalidate_caches()
            self.browser_var.set(True)
            self.status.config(text="Real browser audit is ready.")
            messagebox.showinfo(APP_NAME, "Installed. The next analysis will open the page in a "
                                          "real mobile browser.\n\nIf you have neither Chrome nor "
                                          "Edge, run once in a terminal:\n"
                                          "python -m playwright install chromium")
        else:
            self.status.config(text="Install failed.")
            messagebox.showerror(APP_NAME, "Could not install automatically. Open a terminal and "
                                           "run:\n\npip install playwright\n\n" + msg)

    def fix(self):
        r = self.ensure_selected()
        if not r:
            return
        c = CHECKS[r["id"]]
        top = tk.Toplevel(self)
        top.title(f"Help me fix – {c['title']}")
        top.configure(bg=C["bg"])
        btns = ttk.Frame(top, padding=(20, 0, 20, 20))
        btns.pack(side="bottom", fill="x")
        t = styled_text(top, height=24)
        t.pack(fill="both", expand=True, padx=20, pady=(20, 10))
        t.insert("end", f"Let's fix: {c['title']}\n", "h1")
        t.insert("end", f"Goal: {c['change']}.\n", "muted")
        t.insert("end", "Steps\n", "h2")
        for i, s in enumerate(c["fix"], 1):
            t.insert("end", f"{i}.  {s}\n\n")
        if c.get("code"):
            t.insert("end", "Code you can paste\n", "h2")
            t.insert("end", c["code"] + "\n", "code")
        t.insert("end", "Ask an AI assistant\n", "h2")
        t.insert("end", "Press 'Copy AI prompt' and paste it into Claude or any AI assistant "
                        "for instructions tailored to your theme.\n", "muted")
        t.insert("end", "After the change\n", "h2")
        t.insert("end", "Check the page on mobile, then compare conversion and revenue per visitor "
                        "before and after (or run an A/B test if you have enough traffic).\n")
        t.config(state="disabled")

        def copy(txt, what):
            self.clipboard_clear()
            self.clipboard_append(txt)
            self.status.config(text=f"{what} copied to clipboard.")
            messagebox.showinfo(APP_NAME, f"{what} copied to clipboard.", parent=top)

        if c.get("code"):
            ttk.Button(btns, text="Copy code", style="Ghost.TButton",
                       command=lambda: copy(c["code"], "Code")).pack(side="left")
        ttk.Button(btns, text="Copy AI prompt", style="Accent.TButton",
                   command=lambda: copy(ai_prompt(r, self.url), "AI prompt")).pack(side="right")
        top.transient(self)
        center(top, 780, 660)

    def save_report(self):
        if not self.results:
            messagebox.showinfo(APP_NAME, "Run an analysis first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".html", initialfile="cro_report.html",
                                            filetypes=[("Web page (share or print)", "*.html"),
                                                       ("Text", "*.txt"), ("JSON", "*.json")])
        if not path:
            return
        if path.endswith(".html"):
            Path(path).write_text(html_report(self), encoding="utf-8")
            if messagebox.askyesno(APP_NAME, f"Report saved:\n{path}\n\nOpen it now?"):
                webbrowser.open(Path(path).as_uri())
            return
        if path.endswith(".json"):
            data = {"url": self.url, "notes": self.notes, "results": [
                {**r, "title": CHECKS[r["id"]]["title"],
                 "hypothesis": None if r["passed"] else hypothesis(r),
                 "evidence": [evidence_line(s) for s in self.evidence_for(r["id"])]} for r in self.results]}
            Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            lines = [f"Shopify CRO report – {self.url}", ""]
            for r in sorted(self.results, key=lambda x: x["passed"]):
                c = CHECKS[r["id"]]
                lines.append(f"[{'OK ' if r['passed'] else 'FIX'}] {c['title']} ({r['page']})")
                if not r["passed"]:
                    lines.append(f"      {hypothesis(r)}")
                    for s in self.evidence_for(r["id"]):
                        lines.append(f"      Evidence – {evidence_line(s)}")
                lines.append("")
            if self.notes:
                lines += ["Notes:"] + [f"- {n}" for n in self.notes]
            Path(path).write_text("\n".join(lines), encoding="utf-8")
        messagebox.showinfo(APP_NAME, f"Report saved:\n{path}")


def draw_how_it_works(cv):
    """Flow diagram of how the app works. Boxes size themselves to their text, so the
    layout holds with any font or screen scaling."""
    W = 720
    LX, RX, BW = 40, 390, 290

    def text_box(x, y, w, title, sub="", dark=False):
        col = "#FFFFFF" if dark else "#0A0A0A"
        t = cv.create_text(x + w / 2, y + 10, text=title, anchor="n", fill=col, width=w - 20,
                           justify="center", font=(FONT, 10, "bold"))
        bottom = cv.bbox(t)[3]
        if sub:
            st = cv.create_text(x + w / 2, bottom + 4, text=sub, anchor="n", width=w - 20,
                                justify="center", fill="#D4D4D4" if dark else "#525252",
                                font=(FONT, 9))
            bottom = cv.bbox(st)[3]
        h = bottom - y + 10
        r = cv.create_rectangle(x, y, x + w, y + h, fill="#0A0A0A" if dark else "#FFFFFF",
                                outline="#0A0A0A", width=2)
        cv.tag_lower(r)
        return h, r

    def even(pairs, y):
        """Give boxes in one row the same height."""
        h = max(p[0] for p in pairs)
        for _, r in pairs:
            x1, y1, x2, _ = cv.coords(r)
            cv.coords(r, x1, y1, x2, y + h)
        return h

    def arrow(x1, y1, x2, y2):
        cv.create_line(x1, y1, x2, y2, fill="#0A0A0A", width=2, arrow="last", arrowshape=(9, 11, 4))

    def step(n, x, y):
        cv.create_oval(x - 11, y - 11, x + 11, y + 11, fill="#0A0A0A", outline="")
        cv.create_text(x, y, text=str(n), fill="#FFFFFF", font=(FONT, 9, "bold"))

    y = 12
    h = even([text_box(LX, y, BW, "Store or product link", dark=True),
              text_box(RX, y, BW, "Analytics CSV (GA4 / Shopify)", dark=True)], y)
    arrow(LX + BW / 2, y + h, LX + BW / 2, y + h + 20)
    arrow(RX + BW / 2, y + h, RX + BW / 2, y + h + 20)

    y += h + 20
    h = even([text_box(LX, y, BW, "Collect the pages",
                       "Homepage · a product page · product data · speed · optional real phone "
                       "browser with screenshot"),
              text_box(RX, y, BW, "Read the data",
                       "Sessions, purchases, revenue, add-to-carts and checkouts by device, "
                       "channel or landing page")], y)
    step(1, LX - 18, y + h / 2)
    arrow(LX + BW / 2, y + h, LX + BW / 2, y + h + 20)
    arrow(RX + BW / 2, y + h, RX + BW / 2, y + h + 20)

    y += h + 20
    h = even([text_box(LX, y, BW, "Run the checks",
                       "Simple rules look for reviews, shipping info, trust signals, Shop Pay, "
                       "tracking, speed…"),
              text_box(RX, y, BW, "Compare segments",
                       "Mobile vs desktop · weak channels · low-engagement landing pages · cart "
                       "and checkout drop-off")], y)
    step(2, LX - 18, y + h / 2)
    y_merge = y + h + 34
    arrow(LX + BW / 2, y + h, W / 2 + 15, y_merge)
    arrow(RX + BW / 2, y + h, W / 2 + 15, y_merge)

    y = y_merge
    h, _ = text_box(W / 2 - 145, y, 320, "Each item:  ✓ OK   or   ✗ Fix")
    step(3, W / 2 - 165, y + h / 2)
    arrow(W / 2 + 15, y + h, W / 2 + 15, y + h + 20)

    y += h + 20
    h, _ = text_box(90, y, W - 130, "Explain and rank every 'Fix'",
                    "Why it matters · how it was checked · a hypothesis for an A/B test · evidence "
                    "from your Sources list · ICE priority = (Impact + Confidence + Ease) ÷ 3, where "
                    "confidence grows with the number of supporting sources")
    step(4, 72, y + h / 2)
    y += h
    arrow(W / 2 + 15, y, W / 2 + 15, y + 18)

    y += 18
    outs = [("Open visual audit", "marked screenshot, sketch or chart"),
            ("Help me fix this", "steps · code · AI prompt"),
            ("UX/dev brief", "ready for the team"),
            ("Report & A/B tools", "share · plan · read results")]
    ow, gap = 150, 12
    x0 = (W - (4 * ow + 3 * gap)) / 2 + 20
    cv.create_line(x0 + ow / 2, y, x0 + 3 * (ow + gap) + ow / 2, y, fill="#0A0A0A", width=2)
    boxes = []
    for i, (t, sub) in enumerate(outs):
        x = x0 + i * (ow + gap)
        arrow(x + ow / 2, y, x + ow / 2, y + 16)
        boxes.append(text_box(x, y + 16, ow, t, sub))
    h = even(boxes, y + 16)
    step(5, x0 - 18, y + 16 + h / 2)
    y += 16 + h + 18
    note = cv.create_text(W / 2 + 20, y, anchor="n", width=W - 40, justify="center", fill="#525252",
                          font=(FONT, 9),
                          text="Runs on your computer. Outside calls: the store itself and, only if you "
                               "switch them on, Google PageSpeed and your AI provider.")
    return cv.bbox(note)[3] + 16


class AuditWindow(tk.Toplevel):
    """Real mobile screenshot with numbered markers and the first-screen line."""

    def __init__(self, app, audit, focus=None):
        super().__init__(app)
        self.title("Visual audit – real mobile page")
        self.configure(bg=C["bg"])
        self.audit = audit
        try:
            self.img = tk.PhotoImage(file=audit["shot"])
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not open the screenshot:\n{e}", parent=self)
            self.destroy()
            return
        head = ttk.Frame(self, padding=(20, 16, 20, 6))
        head.pack(fill="x")
        ttk.Label(head, text="Visual audit", font=(FONT, 15, "bold")).pack(anchor="w")
        ttk.Label(head, text=f"{audit['url']}  ·  opened as a phone screen (390×844)",
                  style="Muted.TLabel").pack(anchor="w")

        body = ttk.Frame(self, padding=(20, 6, 20, 20))
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        shot = ttk.Frame(body)
        shot.grid(row=0, column=0, sticky="ns")
        self.cv = tk.Canvas(shot, width=self.img.width() + 2, height=640, bg="#FFFFFF",
                            highlightthickness=1, highlightbackground=C["line"])
        sb = ttk.Scrollbar(shot, command=self.cv.yview)
        self.cv.configure(yscrollcommand=sb.set, scrollregion=(0, 0, self.img.width(), self.img.height()))
        sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="y", expand=True)
        self.cv.create_image(1, 0, image=self.img, anchor="nw")
        self.cv.bind("<MouseWheel>", lambda e: self.cv.yview_scroll(int(-e.delta / 120), "units"))
        self.cv.bind("<Button-4>", lambda e: self.cv.yview_scroll(-3, "units"))
        self.cv.bind("<Button-5>", lambda e: self.cv.yview_scroll(3, "units"))

        t = styled_text(body, height=20)
        t.grid(row=0, column=1, sticky="nsew", padx=(16, 0))
        t.insert("end", "What the markers mean\n", "h1")
        t.insert("end", "Dashed line: where the first phone screen ends.  Red circle: this should "
                        "change.  White marker: found, looks fine.\n", "muted")
        t.tag_config("link", underline=False)
        for item in audit["legend"]:
            num = f"{item['n']}." if item["n"] else "–"
            tag = "mark" if item["bad"] else ""
            line = f"{num}  {item['label']}: {item['status']}\n"
            start = t.index("end-1c")
            t.insert("end", line, tag)
            if item.get("y") is not None:
                end = t.index("end-1c")
                name = f"go{item['key']}"
                t.tag_add(name, start, end)
                t.tag_bind(name, "<Button-1>", lambda e, y=item["y"]: self.scroll_to(y))
                t.tag_bind(name, "<Enter>", lambda e: t.config(cursor="hand2"))
                t.tag_bind(name, "<Leave>", lambda e: t.config(cursor=""))
        t.insert("end", "\nClick a line to jump to it in the screenshot.\n", "muted")
        if audit.get("cut"):
            t.insert("end", "Very long page: the screenshot shows the first 6,000 pixels.\n", "muted")
        t.insert("end", "Pop-ups or cookie banners can cover parts of the page in the screenshot.\n",
                 "muted")
        t.config(state="disabled")

        btns = ttk.Frame(self, padding=(20, 0, 20, 18))
        btns.pack(side="bottom", fill="x", before=body)
        ttk.Button(btns, text="Open full-size image", style="Ghost.TButton",
                   command=lambda: open_location(audit["shot"])).pack(side="left")
        ttk.Button(btns, text="Save image as…", style="Ghost.TButton",
                   command=self.save).pack(side="left", padx=8)
        self.transient(app)
        center(self, min(1000, self.winfo_screenwidth() - 60), min(820, self.winfo_screenheight() - 80))
        if focus:
            item = next((i for i in audit["legend"] if i["key"] == focus and i.get("y") is not None), None)
            if item:
                self.after(150, lambda: self.scroll_to(item["y"]))

    def scroll_to(self, y):
        h = max(self.img.height(), 1)
        self.cv.yview_moveto(max(0, (y - 120) / h))

    def save(self):
        import shutil
        p = filedialog.asksaveasfilename(parent=self, defaultextension=".png",
                                         initialfile=Path(self.audit["shot"]).name,
                                         filetypes=[("PNG image", "*.png")])
        if p:
            shutil.copyfile(self.audit["shot"], p)
            messagebox.showinfo(APP_NAME, f"Saved:\n{p}", parent=self)


class HelpWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.title("Help, FAQ & Contact")
        self.configure(bg=C["bg"])
        ttk.Label(self, text="Help, FAQ & Contact", font=(FONT, 15, "bold")).pack(anchor="w", padx=20, pady=(18, 0))
        ttk.Label(self, text="Quick answers, plain-language explanations and a way to reach us.",
                  style="Muted.TLabel").pack(anchor="w", padx=20, pady=(2, 10))
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        f0 = ttk.Frame(nb, padding=(0, 10, 0, 0))
        nb.add(f0, text="  How it works  ")
        cv = tk.Canvas(f0, width=760, height=620, bg=C["card"], highlightthickness=1,
                       highlightbackground=C["line"])
        csb = ttk.Scrollbar(f0, command=cv.yview)
        cv.configure(yscrollcommand=csb.set)
        csb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)
        h = draw_how_it_works(cv)
        cv.configure(scrollregion=(0, 0, 760, h), height=min(h, self.winfo_screenheight() - 260))
        cv.bind("<MouseWheel>", lambda e: cv.yview_scroll(int(-e.delta / 120), "units"))

        f1 = ttk.Frame(nb, padding=(0, 8, 0, 0))
        nb.add(f1, text="  FAQ  ")
        t1 = styled_text(f1, height=28)
        t1.pack(fill="both", expand=True)
        for q, a_ in FAQ:
            t1.insert("end", q + "\n", "h2")
            t1.insert("end", a_ + "\n")
        t1.config(state="disabled")

        f2 = ttk.Frame(nb, padding=(0, 8, 0, 0))
        nb.add(f2, text="  Glossary  ")
        t2 = styled_text(f2, height=28)
        t2.pack(fill="both", expand=True)
        for term, text in GLOSSARY:
            t2.insert("end", term + "\n", "h2")
            t2.insert("end", text + "\n")
        t2.insert("end", "Where do the results come from?\n", "h2")
        t2.insert("end", "Every check uses a simple, transparent rule (see 'How this was checked' on "
                         "each item, or the 'Check rules' tab in Sources). Evidence comes from the "
                         "sources list, which you can edit.\n")
        t2.config(state="disabled")

        f3 = ttk.Frame(nb, padding=(4, 14, 4, 4))
        nb.add(f3, text="  Contact us  ")
        f3.columnconfigure(1, weight=1)
        ttk.Label(f3, text="Questions, ideas or a bug to report? Send a message.",
                  font=(FONT, 11, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(f3, text=f"Email: {CONTACT_EMAIL}", style="Muted.TLabel").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(2, 14))
        ttk.Label(f3, text="Your name").grid(row=2, column=0, sticky="w", pady=6, padx=(0, 12))
        name_v = tk.StringVar()
        ttk.Entry(f3, textvariable=name_v).grid(row=2, column=1, columnspan=2, sticky="ew")
        ttk.Label(f3, text="Topic").grid(row=3, column=0, sticky="w", pady=6)
        topic_v = tk.StringVar(value="Question")
        ttk.Combobox(f3, textvariable=topic_v, state="readonly", width=24,
                     values=["Question", "Feature idea", "Bug report", "Other"]).grid(
            row=3, column=1, sticky="w")
        ttk.Label(f3, text="Message").grid(row=4, column=0, sticky="nw", pady=6)
        msg = scroll_text(f3, height=10, wrap="word", font=(FONT, 10), relief="flat",
                      highlightthickness=1, highlightbackground=C["line"],
                      highlightcolor=C["text"])
        msg.grid(row=4, column=1, columnspan=2, sticky="nsew", pady=6)
        f3.rowconfigure(4, weight=1)
        ttk.Label(f3, text="'Send email' opens your email app with the message ready to send.",
                  style="Muted.TLabel").grid(row=5, column=1, columnspan=2, sticky="w")

        def send():
            from urllib.parse import quote
            body = msg.get("1.0", "end").strip()
            if not body:
                messagebox.showwarning(APP_NAME, "Please write a message first.", parent=self)
                return
            if name_v.get().strip():
                body += f"\n\n– {name_v.get().strip()}"
            if app.url:
                body += f"\n\n(Store checked: {app.url})"
            subject = f"{APP_NAME}: {topic_v.get()}"
            webbrowser.open(f"mailto:{CONTACT_EMAIL}?subject={quote(subject)}&body={quote(body)}")

        def copy_addr():
            self.clipboard_clear()
            self.clipboard_append(CONTACT_EMAIL)
            messagebox.showinfo(APP_NAME, "Email address copied.", parent=self)

        b = ttk.Frame(f3)
        b.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(14, 0))
        ttk.Button(b, text="Copy email address", style="Ghost.TButton",
                   command=copy_addr).pack(side="left")
        ttk.Button(b, text="Send email", style="Accent.TButton", command=send).pack(side="right")

        self.transient(app)
        self.update_idletasks()
        center(self, 860, min(self.winfo_reqheight() + 20, self.winfo_screenheight() - 80))


class AISettingsWindow(tk.Toplevel):
    """Choose the AI provider for reading sources and enter your own key."""

    def __init__(self, app, on_saved=None):
        super().__init__(app)
        self.app, self.on_saved = app, on_saved
        self.title("AI add-on settings")
        self.configure(bg=C["bg"])
        self.settings = load_settings()
        b = ttk.Frame(self, padding=(22, 10, 22, 20))
        b.pack(fill="x", side="bottom")
        sf = ScrollFrame(self, padding=(22, 22, 8, 0))
        sf.pack(fill="both", expand=True)
        f = sf.inner
        ttk.Label(f, text="AI add-on: read sources for you", font=(FONT, 15, "bold")).pack(anchor="w")
        ttk.Label(f, text="Optional. When you add a source, the AI reads it and lists the findings it "
                          "contains, whether they support each idea, and which checks they relate to. You "
                          "review everything before it is saved. The rest of the app works without it.",
                  style="Muted.TLabel", wraplength=640, justify="left").pack(anchor="w", pady=(4, 14))

        ttk.Label(f, text="1. Choose a provider", font=(FONT, 11, "bold")).pack(anchor="w")
        self.provider = tk.StringVar(value=self.settings.get("provider", "claude"))
        for key, info in AI_PROVIDERS.items():
            row = ttk.Frame(f)
            row.pack(fill="x", pady=(6, 0))
            ttk.Radiobutton(row, text=info["name"], value=key, variable=self.provider,
                            command=self._show).pack(side="left")
            ttk.Label(row, text="   " + info["tag"], style="Muted.TLabel").pack(side="left")

        ttk.Label(f, text="2. Connect it", font=(FONT, 11, "bold")).pack(anchor="w", pady=(16, 4))
        self.box = ttk.Frame(f)
        self.box.pack(fill="x")
        self.note = ttk.Label(f, style="Muted.TLabel", wraplength=640, justify="left")
        self.note.pack(anchor="w", pady=(10, 0))
        ttk.Label(f, text="Your key is saved only on this computer, in your user folder – never "
                          "inside the app file or on GitHub.", style="Muted.TLabel",
                  wraplength=640, justify="left").pack(anchor="w", pady=(6, 0))
        self.result = ttk.Label(f, text="", wraplength=640, justify="left")
        self.result.pack(anchor="w", pady=(12, 0))

        ttk.Button(b, text="Test connection", style="Ghost.TButton", command=self._test).pack(side="left")
        ttk.Button(b, text="Save", style="Accent.TButton", command=self._save).pack(side="right")
        ttk.Button(b, text="Cancel", style="Ghost.TButton", command=self.destroy).pack(side="right", padx=8)
        self.vars = {}
        self._show()
        self.transient(app)
        center(self, 720, 640)

    def _show(self):
        for w in self.box.winfo_children():
            w.destroy()
        p = self.provider.get()
        info = AI_PROVIDERS[p]
        self.box.columnconfigure(1, weight=1)
        r = 0
        if p in ("claude", "gemini"):
            ttk.Label(self.box, text="API key").grid(row=r, column=0, sticky="w", padx=(0, 12), pady=5)
            v = tk.StringVar(value=self.settings.get(f"{p}_key", ""))
            self.vars[f"{p}_key"] = v
            e = ttk.Entry(self.box, textvariable=v, show="•")
            e.grid(row=r, column=1, sticky="ew")
            show = tk.BooleanVar(value=False)
            ttk.Checkbutton(self.box, text="Show", variable=show,
                            command=lambda: e.config(show="" if show.get() else "•")).grid(
                row=r, column=2, padx=(8, 0))
            r += 1
        else:
            ttk.Label(self.box, text="Address").grid(row=r, column=0, sticky="w", padx=(0, 12), pady=5)
            v = tk.StringVar(value=self.settings.get("ollama_url", "http://localhost:11434"))
            self.vars["ollama_url"] = v
            ttk.Entry(self.box, textvariable=v).grid(row=r, column=1, sticky="ew")
            r += 1
        ttk.Label(self.box, text="Model").grid(row=r, column=0, sticky="w", padx=(0, 12), pady=5)
        mv = tk.StringVar(value=self.settings.get(f"{p}_model", info["models"][0]))
        self.vars[f"{p}_model"] = mv
        ttk.Combobox(self.box, textvariable=mv, values=info["models"], width=30).grid(
            row=r, column=1, sticky="w")
        r += 1
        link = ttk.Label(self.box, text=("Get an API key →" if p != "ollama" else "Download Ollama →"),
                         foreground=C["text"], cursor="hand2", font=(FONT, 10, "underline"))
        link.grid(row=r, column=1, sticky="w", pady=(6, 0))
        link.bind("<Button-1>", lambda e: webbrowser.open(info["key_url"]))
        self.note.config(text=info["note"])
        self.result.config(text="")

    def _collect(self):
        s = dict(self.settings)
        s["provider"] = self.provider.get()
        for k, v in self.vars.items():
            s[k] = v.get().strip()
        return s

    def _test(self):
        s = self._collect()
        if not ai_ready(s):
            self.result.config(text="Please enter an API key first.", foreground=MARK)
            return
        self.result.config(text="Testing…", foreground=C["muted"])

        def work():
            try:
                out = call_ai(s, "Reply with the single word OK.", max_tokens=20)
                msg, col = f"Connected. The model replied: {out.strip()[:40]}", C["text"]
            except Exception as e:
                msg, col = f"Could not connect: {str(e)[:300]}", MARK
            self.after(0, lambda: self.result.config(text=msg, foreground=col))
        threading.Thread(target=work, daemon=True).start()

    def _save(self):
        self.settings = self._collect()
        try:
            save_settings(self.settings)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not save settings:\n{e}", parent=self)
            return
        if self.on_saved:
            self.on_saved()
        self.destroy()


class FindingsReview(tk.Toplevel):
    """Shows what the AI found in a source; the user picks what to keep."""

    def __init__(self, parent, result, on_use):
        super().__init__(parent)
        self.title("Findings found in this source")
        self.configure(bg=C["bg"])
        self.result, self.on_use = result, on_use
        head = ttk.Frame(self, padding=(22, 18, 22, 6))
        head.pack(fill="x")
        ttk.Label(head, text="What the AI found", font=(FONT, 15, "bold")).pack(anchor="w")
        if result.get("summary"):
            ttk.Label(head, text=result["summary"], wraplength=720, justify="left").pack(anchor="w", pady=(4, 0))
        ttk.Label(head, text="Tick the findings you want to keep and check them against the source – AI "
                             "can misread numbers. Findings that contradict an idea are kept as "
                             "warnings and lower its priority.",
                  style="Muted.TLabel", wraplength=720, justify="left").pack(anchor="w", pady=(6, 0))

        b = ttk.Frame(self, padding=(22, 8, 22, 18))
        b.pack(side="bottom", fill="x")
        ttk.Button(b, text="Use selected findings", style="Accent.TButton",
                   command=self._use).pack(side="right")
        ttk.Button(b, text="Cancel", style="Ghost.TButton", command=self.destroy).pack(side="right", padx=8)

        outer = ttk.Frame(self, padding=(22, 6, 22, 0))
        outer.pack(fill="both", expand=True)
        cv = tk.Canvas(outer, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
        sb = ttk.Scrollbar(outer, command=cv.yview)
        inner = tk.Frame(cv, bg=C["card"])
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0, 0), window=inner, anchor="nw", width=720)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)

        self.vars = []
        labels = {"positive": "SUPPORTS THE IDEA", "negative": "CONTRADICTS THE IDEA",
                  "no_effect": "NO CLEAR EFFECT"}
        if not result["findings"]:
            tk.Label(inner, text="No concrete CRO findings with evidence were found in this source.",
                     bg=C["card"], fg=C["muted"], font=(FONT, 10)).pack(anchor="w", padx=14, pady=14)
        for f in result["findings"]:
            v = tk.BooleanVar(value=bool(f["checks"]))
            self.vars.append(v)
            row = tk.Frame(inner, bg=C["card"])
            row.pack(fill="x", padx=12, pady=(10, 2))
            tk.Checkbutton(row, variable=v, bg=C["card"], activebackground=C["card"]).pack(side="left", anchor="n")
            body = tk.Frame(row, bg=C["card"])
            body.pack(side="left", fill="x", expand=True)
            tag = labels.get(f["effect"], "SUPPORTS THE IDEA")
            tk.Label(body, text=f" {tag} ", bg="#0A0A0A" if f["effect"] == "positive" else MARK,
                     fg="#FFFFFF", font=(FONT, 8, "bold")).pack(anchor="w")
            tk.Label(body, text=f["text"], bg=C["card"], fg=C["text"], font=(FONT, 10),
                     wraplength=640, justify="left").pack(anchor="w", pady=(3, 0))
            names = ", ".join(CHECKS[c]["title"] for c in f["checks"]) or "no matching check"
            tk.Label(body, text=f"Supports: {names}   ·   confidence: {f.get('confidence', '')}",
                     bg=C["card"], fg=C["muted"], font=(FONT, 9), wraplength=640,
                     justify="left").pack(anchor="w")
        self.transient(parent)
        center(self, 800, 640)

    def _use(self):
        chosen = [f for f, v in zip(self.result["findings"], self.vars) if v.get()]
        if not chosen:
            messagebox.showwarning(APP_NAME, "Tick at least one finding.", parent=self)
            return
        self.on_use(self.result, chosen)
        self.destroy()


class SourcesWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Sources – what the checks are based on")
        self.configure(bg=C["bg"])
        ttk.Label(self, text="Sources", font=(FONT, 15, "bold")).pack(anchor="w", padx=20, pady=(18, 0))
        intro = tk.Frame(self, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
        intro.pack(fill="x", padx=20, pady=(8, 10))
        for title, text in [
                ("What is a source?", "A study, article or case study showing that a change on an "
                                      "online store worked – or didn't."),
                ("What does it do here?", "It appears as evidence under the checks it relates to, and "
                                          "ideas with more support move up the priority list. Findings "
                                          "that contradict an idea lower its priority and show as a warning."),
                ("What doesn't it do?", "It does not change what the app checks on a store. Those rules "
                                        "are listed in the 'Check rules' tab."),
                ("Credits", "Built-in findings are short summaries in our own words, with a link to "
                            "the original. All rights belong to their authors; this app is not "
                            "affiliated with them.")]:
            row = tk.Frame(intro, bg=C["card"])
            row.pack(fill="x", padx=14, pady=3)
            tk.Label(row, text=title, bg=C["card"], fg=C["text"], font=(FONT, 10, "bold"),
                     width=20, anchor="w").pack(side="left", anchor="n")
            tk.Label(row, text=text, bg=C["card"], fg=C["navy2"], font=(FONT, 10), justify="left",
                     anchor="w", wraplength=640).pack(side="left", fill="x")
        b = ttk.Frame(self, padding=(20, 0, 20, 18))
        b.pack(side="bottom", fill="x")
        ttk.Button(b, text="Add", style="Accent.TButton", command=lambda: AddSource(self)).pack(side="left")
        ttk.Button(b, text="Remove", style="Ghost.TButton", command=self.remove).pack(side="left", padx=8)
        ttk.Button(b, text="Open", style="Ghost.TButton", command=self.open_sel).pack(side="left")
        ttk.Button(b, text="Restore defaults", style="Ghost.TButton",
                   command=self.restore).pack(side="right")
        ttk.Button(b, text="AI add-on settings", style="Ghost.TButton",
                   command=lambda: AISettingsWindow(self.app)).pack(side="right", padx=8)
        self.info = scroll_text(self, height=4, wrap="word", font=(FONT, 10), bg=C["card"],
                                fg=C["navy2"], relief="flat", padx=10, pady=8, highlightthickness=1,
                                highlightbackground=C["line"], cursor="arrow")
        self.info.pack(side="bottom", fill="x", padx=20, pady=8)
        self._set_info("Select a source to see its finding.")
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=20)
        wrap = ttk.Frame(nb, padding=(0, 8, 0, 0))
        nb.add(wrap, text="  Evidence sources  ")
        rules_tab = ttk.Frame(nb, padding=(0, 8, 0, 0))
        nb.add(rules_tab, text="  Check rules  ")
        rt = ttk.Treeview(rules_tab, columns=("rule", "n"), show="tree headings")
        rt.heading("#0", text="Check", anchor="w")
        rt.heading("rule", text="How it is evaluated", anchor="w")
        rt.heading("n", text="Sources", anchor="w")
        rt.column("#0", width=230, stretch=False)
        rt.column("rule", width=460)
        rt.column("n", width=70, stretch=False)
        rsb = ttk.Scrollbar(rules_tab, command=rt.yview)
        rt.configure(yscrollcommand=rsb.set)
        rsb.pack(side="right", fill="y")
        rt.pack(side="left", fill="both", expand=True)
        self.rules_tree = rt
        rt.bind("<<TreeviewSelect>>", lambda e: self.preview_rule())
        self.tree = ttk.Treeview(wrap, columns=("type", "checks"), show="tree headings")
        self.tree.heading("#0", text="Title", anchor="w")
        self.tree.heading("type", text="Type", anchor="w")
        self.tree.heading("checks", text="Used by", anchor="w")
        self.tree.column("#0", width=440)
        self.tree.column("type", width=100, stretch=False)
        self.tree.column("checks", width=100, stretch=False)
        sb = ttk.Scrollbar(wrap, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.preview())
        self.tree.bind("<Double-1>", lambda e: self.open_sel())
        self.refresh()
        self.transient(app)
        center(self, 900, 720)

    def _set_info(self, text):
        self.info.config(state="normal")
        self.info.delete("1.0", "end")
        self.info.insert("1.0", text)
        self.info.config(state="disabled")
        self.info.yview_moveto(0)

    def refresh(self):
        self.rules_tree.delete(*self.rules_tree.get_children())
        for cid, c in CHECKS.items():
            n = len([x for x in self.app.sources if cid in x.get("checks", [])])
            self.rules_tree.insert("", "end", iid=cid, text="  " + c["title"],
                                   values=(CHECK_RULES.get(cid, ""), n))
        self.tree.delete(*self.tree.get_children())
        for i, s in enumerate(self.app.sources):
            self.tree.insert("", "end", iid=str(i), text="  " + s["title"],
                             values=(s.get("type", ""), f"{len(s.get('checks', []))} check" + ("" if len(s.get('checks', [])) == 1 else "s")))
        self._set_info("Select a source to see its finding. Double-click to open it.")

    def sel(self):
        s = self.tree.selection()
        return int(s[0]) if s else None

    def preview(self):
        i = self.sel()
        if i is None:
            return
        s = self.app.sources[i]
        names = ", ".join(CHECKS[c]["title"] for c in s.get("checks", []) if c in CHECKS)
        extra = ""
        if s.get("findings"):
            extra = "\n" + "\n".join(f"• {EFFECT_PREFIX.get(f.get('effect'), '')}{f['text']}"
                                      for f in s["findings"][:4])
        self._set_info(f"{s.get('finding', '')}{extra}\n\nLocation: {s.get('location') or '—'}\n"
                              f"Used by: {names or '—'}")

    def preview_rule(self):
        sel = self.rules_tree.selection()
        if not sel:
            return
        cid = sel[0]
        srcs = [x["title"] for x in self.app.sources if cid in x.get("checks", [])]
        self._set_info(f"{CHECKS[cid]['title']}: {CHECK_RULES.get(cid, '')}\n\n"
                              f"Evidence: {'; '.join(srcs) or 'none linked yet – use Add to link a source'}")

    def open_sel(self):
        i = self.sel()
        if i is not None:
            open_location(self.app.sources[i].get("location", ""))

    def remove(self):
        i = self.sel()
        if i is None:
            return
        s = self.app.sources[i]
        if messagebox.askyesno(APP_NAME, f"Remove this source?\n\n{s['title']}", parent=self):
            del self.app.sources[i]
            save_sources(self.app.sources)
            self.refresh()
            self.app.refresh_priorities()

    def restore(self):
        if messagebox.askyesno(APP_NAME, "Bring back any removed built-in sources? Your own "
                                         "sources will be kept.", parent=self):
            ids = {s.get("id") for s in self.app.sources}
            for d in DEFAULT_SOURCES:
                if d["id"] not in ids:
                    self.app.sources.append(dict(d))
            save_sources(self.app.sources)
            self.refresh()


class AddSource(tk.Toplevel):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.title("Add source")
        self.configure(bg=C["bg"])
        self.ai_findings = None
        b = ttk.Frame(self, padding=(20, 10, 20, 18))
        b.pack(side="bottom", fill="x")
        ttk.Button(b, text="Save source", style="Accent.TButton", command=self.save).pack(side="right")
        ttk.Button(b, text="Cancel", style="Ghost.TButton", command=self.destroy).pack(side="right", padx=8)
        sf = ScrollFrame(self)
        sf.pack(fill="both", expand=True)
        guide = tk.Frame(sf.inner, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
        guide.pack(fill="x", padx=20, pady=(18, 0))
        tk.Label(guide, text="Add research that backs up a check", bg=C["card"], fg=C["text"],
                 font=(FONT, 11, "bold")).pack(anchor="w", padx=14, pady=(10, 2))
        tk.Label(guide, text="1  Paste a link or pick a file (PDF, Word or text).\n"
                             "2  Write what it found – or press 'Read with AI' to let the AI add-on "
                             "list the findings for you.\n"
                             "3  Choose which checks it supports, then Save.",
                 bg=C["card"], fg=C["navy2"], font=(FONT, 10), justify="left").pack(
            anchor="w", padx=14, pady=(0, 10))
        f = ttk.Frame(sf.inner, padding=20)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)
        f.rowconfigure(5, weight=1)

        ttk.Label(f, text="Title").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 12))
        self.title_v = tk.StringVar()
        ttk.Entry(f, textvariable=self.title_v).grid(row=0, column=1, columnspan=3, sticky="ew")

        ttk.Label(f, text="Type").grid(row=1, column=0, sticky="w", pady=6)
        self.type_v = tk.StringVar(value="Website")
        ttk.Combobox(f, textvariable=self.type_v, state="readonly",
                     values=["Website", "PDF", "Document", "Case study", "Other"]).grid(
            row=1, column=1, sticky="w")

        ttk.Label(f, text="Link or file").grid(row=2, column=0, sticky="w", pady=6)
        self.loc_v = tk.StringVar()
        ttk.Entry(f, textvariable=self.loc_v).grid(row=2, column=1, sticky="ew")
        ttk.Button(f, text="Browse…", style="Ghost.TButton", command=self.browse).grid(
            row=2, column=2, padx=(8, 0))
        ai_row = ttk.Frame(f)
        ai_row.grid(row=2, column=3, padx=(8, 0))
        self.b_ai = ttk.Button(ai_row, text="Read with AI", style="Accent.TButton", command=self.read_ai)
        self.b_ai.pack()
        Tooltip(self.b_ai, "AI add-on: reads the source and lists its findings, whether they support "
                           "each idea, and which checks they relate to. Uses your own API key or a "
                           "free local model (see AI add-on settings).")
        self.ai_status = ttk.Label(f, text=self._ai_label(), style="Muted.TLabel")
        self.ai_status.grid(row=8, column=0, columnspan=4, sticky="w", pady=(10, 0))

        ttk.Label(f, text="What did it find?").grid(row=3, column=0, sticky="nw", pady=6)
        self.find_t = scroll_text(f, height=4, wrap="word", font=(FONT, 10), relief="flat",
                              highlightthickness=1, highlightbackground=C["line"])
        self.find_t.grid(row=3, column=1, columnspan=3, sticky="ew", pady=6)
        ttk.Label(f, text="One or two sentences, e.g. 'Adding X lifted conversion by 10%'.",
                  style="Muted.TLabel").grid(row=4, column=1, columnspan=3, sticky="w")

        ttk.Label(f, text="Which checks\ndoes it support?", justify="left").grid(
            row=5, column=0, sticky="nw", pady=(12, 6))
        self.ids = list(CHECKS.keys())
        lb_wrap = ttk.Frame(f)
        lb_wrap.grid(row=5, column=1, columnspan=3, sticky="nsew", pady=(12, 6))
        self.lb = tk.Listbox(lb_wrap, selectmode="multiple", height=9, font=(FONT, 10),
                             relief="flat", highlightthickness=1, highlightbackground=C["line"],
                             exportselection=False, selectbackground="#E5E5E5",
                             selectforeground=C["text"])
        for k in self.ids:
            self.lb.insert("end", "  " + CHECKS[k]["title"])
        sb = ttk.Scrollbar(lb_wrap, command=self.lb.yview)
        self.lb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.lb.pack(side="left", fill="both", expand=True)
        ttk.Label(f, text="Click to select one or more.", style="Muted.TLabel").grid(
            row=6, column=1, columnspan=3, sticky="w")

        self.transient(win)
        center(self, 820, 760)

    def _ai_label(self):
        st = load_settings()
        name = AI_PROVIDERS.get(st.get("provider"), {}).get("name", "")
        if ai_ready(st):
            return f"AI add-on: {name} is set up."
        return "AI add-on: not set up yet – 'Read with AI' will open the settings (your own key or a free local model)."

    def read_ai(self):
        loc = self.loc_v.get().strip()
        if not loc:
            messagebox.showinfo(APP_NAME, "Paste a link or pick a file first.", parent=self)
            return
        st = load_settings()
        if not ai_ready(st):
            AISettingsWindow(self.win.app, on_saved=lambda: self.ai_status.config(text=self._ai_label()))
            return
        self.b_ai.config(state="disabled")
        self.ai_status.config(text="Reading the source with AI… this can take up to a minute.")

        def work():
            try:
                res = ai_extract(st, loc)
                self.after(0, lambda: self._ai_done(res))
            except Exception as e:
                self.after(0, lambda: self._ai_fail(str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _ai_fail(self, msg):
        self.b_ai.config(state="normal")
        self.ai_status.config(text=self._ai_label())
        if msg == "NEEDS_PYPDF":
            if messagebox.askyesno(APP_NAME, "Reading PDFs needs a small add-on (pypdf). Install it "
                                             "now?", parent=self):
                self.ai_status.config(text="Installing pypdf…")

                def inst():
                    ok, out = pip_install("pypdf")
                    self.after(0, lambda: (self.ai_status.config(text=self._ai_label()),
                                           messagebox.showinfo(APP_NAME, "Installed. Press 'Read with AI' again."
                                                               if ok else "Install failed:\n" + out,
                                                               parent=self)))
                threading.Thread(target=inst, daemon=True).start()
            return
        messagebox.showerror(APP_NAME, f"Could not read this source:\n\n{msg}", parent=self)

    def _ai_done(self, res):
        self.b_ai.config(state="normal")
        self.ai_status.config(text=self._ai_label())
        FindingsReview(self, res, self._use_findings)

    def _use_findings(self, res, chosen):
        self.ai_findings = chosen
        if not self.title_v.get().strip():
            self.title_v.set(res.get("title", ""))
        summary = res.get("summary") or chosen[0]["text"]
        self.find_t.delete("1.0", "end")
        self.find_t.insert("1.0", summary)
        ids = {c for f in chosen for c in f["checks"]}
        self.lb.selection_clear(0, "end")
        for i, k in enumerate(self.ids):
            if k in ids:
                self.lb.selection_set(i)
        n_neg = sum(1 for f in chosen if f["effect"] != "positive")
        self.ai_status.config(text=f"{len(chosen)} finding(s) added from the AI reading"
                                   + (f", {n_neg} as warnings" if n_neg else "") +
                              ". Review the checks below, then Save.")

    def browse(self):
        p = filedialog.askopenfilename(parent=self, filetypes=[
            ("Documents", "*.pdf *.docx *.doc *.txt *.md *.xlsx *.pptx"), ("All files", "*.*")])
        if p:
            self.loc_v.set(p)
            if not self.title_v.get():
                self.title_v.set(Path(p).stem)
            self.type_v.set("PDF" if Path(p).suffix.lower() == ".pdf" else "Document")

    def save(self):
        title = self.title_v.get().strip()
        finding = self.find_t.get("1.0", "end").strip()
        checks = [self.ids[i] for i in self.lb.curselection()]
        if not title or not finding or not checks:
            messagebox.showwarning(APP_NAME, "Please fill in a title, a key finding and pick at "
                                             "least one check.", parent=self)
            return
        existing = {s.get("id") for s in self.win.app.sources}
        n = 1
        while f"user_{n}" in existing:
            n += 1
        src = {"id": f"user_{n}", "title": title, "type": self.type_v.get(),
               "location": self.loc_v.get().strip(), "finding": finding, "checks": checks}
        if self.ai_findings:
            src["findings"] = self.ai_findings
            src["read_with_ai"] = True
        self.win.app.sources.append(src)
        save_sources(self.win.app.sources)
        self.win.refresh()
        self.win.app.refresh_priorities()
        self.destroy()


def enable_dpi():
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


if __name__ == "__main__":
    enable_dpi()
    App().mainloop()
