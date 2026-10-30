"""
Shopify CRO Checker – analysis core.

Everything that does not need a window: the check library, store analysis, the optional
real-browser audit, evidence and ICE scoring, analytics CSV reading, the AI add-on,
briefs, A/B test maths and the HTML report.

Used by both the desktop app (shopify_cro_checker.pyw) and the web app (streamlit_app.py).
"""

import json
import os
import re
import sys
import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

APP_NAME = "Shopify CRO Checker"
CONTACT_EMAIL = "alperhasankizik@gmail.com"   # change this to update the Contact us address
HEADERS = {"User-Agent": "Mozilla/5.0 (Shopify CRO Checker - personal learning project)"}
DATA_DIR = Path.home() / ".shopify_cro_checker"
SOURCES_FILE = DATA_DIR / "sources.json"
MARK = "#DC2626"   # the only colour: a pen-style circle around what should change

# When True (web app), only public internet addresses can be opened.
SAFE_MODE = False


class BlockedURL(ValueError):
    pass


def check_public(url):
    """Refuse links that point to this server or a private network."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise BlockedURL("Only http and https links can be checked.")
    if p.port not in (None, 80, 443):
        raise BlockedURL("Only standard web ports can be checked.")
    try:
        infos = socket.getaddrinfo(p.hostname, None)
    except socket.gaierror:
        raise BlockedURL(f"The address '{p.hostname}' could not be found.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise BlockedURL("This address is not on the public internet.")


def _guard_redirect(r, *args, **kwargs):
    if SAFE_MODE and r.is_redirect:
        check_public(urljoin(r.url, r.headers.get("location", "")))


def _get(url, **kw):
    if SAFE_MODE:
        check_public(url)
    return requests.get(url, headers=HEADERS, hooks={"response": _guard_redirect}, **kw)


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
        return str(e)
    return None


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
    r = _get(url, timeout=timeout)
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
        r = _get(clean + ".json", timeout=20)
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
            return p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"],
                                     **kw)
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
                                   "y": b["y"], "h": b["h"]})
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
                               "bad": bad, "y": b["y"], "h": b["h"]})
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



def html_report(url, results, notes, audit, sources):
    import html as H
    rows = sorted(results, key=lambda r: (r["passed"], -r.get("ice", (0,))[0]))
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
           f"<h1>Shopify CRO report</h1><p class='muted'>{H.escape(url)}</p>",
           f"<p><b>{len(rows) - len(bad)} of {len(rows)}</b> checks passed · <b>{len(bad)}</b> ideas to test</p>",
           "<h2>Ideas to test, by priority</h2>"]
    for r in bad:
        c = CHECKS[r["id"]]
        out.append(f"<div class='card'><span class='score'>{r['ice'][0]:.1f}</span><b>{H.escape(c['title'])}</b>"
                   f" <span class='muted'>· {H.escape(r['page'])}</span>"
                   f"<p>{H.escape(hypothesis(r))}</p>")
        for s_ in evidence_items(sources, r["id"]):
            out.append(f"<p class='ev'>Evidence – {H.escape(evidence_line(s_))}</p>")
        out.append("</div>")
    if audit and Path(audit["shot"]).exists():
        import base64
        data = base64.b64encode(Path(audit["shot"]).read_bytes()).decode()
        out.append("<h2>Visual audit (real mobile page)</h2>"
                   "<p class='muted'>Dashed line: end of the first phone screen. Red circles: what "
                   "should change.</p><div style='display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start'>"
                   f"<img src='data:image/png;base64,{data}' style='width:300px;border:1px solid #e5e5e5'>"
                   "<ol style='flex:1;min-width:240px;padding-left:18px'>")
        for it in audit["legend"]:
            if it["n"]:
                w = "<b style='color:#DC2626'>" if it["bad"] else ""
                we = "</b>" if it["bad"] else ""
                out.append(f"<li value='{it['n']}'>{w}{H.escape(it['label'])}: {H.escape(it['status'])}{we}</li>")
        missing = [it for it in audit["legend"] if not it["n"]]
        out.append("</ol></div>")
        if missing:
            out.append("<p class='muted'>Not found: " + ", ".join(H.escape(m["label"]) for m in missing) + "</p>")
    out.append("<h2>All checks</h2><table><tr><th>Check</th><th>Page</th><th>Result</th></tr>")
    for r in rows:
        out.append(f"<tr><td>{H.escape(CHECKS[r['id']]['title'])}</td><td>{H.escape(r['page'])}</td>"
                   f"<td>{'OK' if r['passed'] else '<b>Fix</b>'}</td></tr>")
    out.append("</table>")
    if notes:
        out.append("<h2>Notes</h2>" + "".join(f"<p class='muted'>{H.escape(n)}</p>" for n in notes))
    out.append("<p class='muted' style='margin-top:40px'>ICE = impact, confidence, ease (1–10). "
               "Results are ideas to test, not guarantees.</p></body></html>")
    return "\n".join(out)
