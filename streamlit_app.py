"""
Shopify CRO Checker – web version (Streamlit).

Paste a store link and get a first-pass CRO audit in the browser. Uses the same check
library and scoring as the desktop app (cro_core.py).

Run locally:  streamlit run streamlit_app.py
"""

import os
import shutil
import tempfile
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import cro_core as core
from cro_core import (CHECKS, CHECK_RULES, DEFAULT_SOURCES, EXPORT_HELP, GLOSSARY,
                      ab_result, ai_prompt, analyze, analyze_data, evidence_items, evidence_line,
                      evidence_score, html_report, hypothesis, ice_score, make_brief, normalize,
                      sample_size)

GITHUB = "https://github.com/akizik1/shopify-cro-checker"
HERE = Path(__file__).parent

# ---------------------------------------------------------------- server set-up
core.SAFE_MODE = os.environ.get("CRO_ALLOW_LOCAL") != "1"   # only public web addresses (local tests can opt out)
WORK_DIR = Path(tempfile.gettempdir()) / "cro_checker"
core.DATA_DIR = WORK_DIR                    # screenshots go to a temp folder, not a home folder
for name in ("chromium", "chromium-browser", "google-chrome"):
    if shutil.which(name):
        core.BROWSER_PATH = shutil.which(name)
        break
SOURCES = DEFAULT_SOURCES                   # the web version uses the built-in sources, read-only

st.set_page_config(page_title="Shopify CRO Checker", page_icon="🛒", layout="wide")

st.html("""
<style>
.block-container { padding-top: 2.2rem; max-width: 1180px; }
h1 { font-weight: 700; letter-spacing: -0.02em; }
.muted { color: #737373; font-size: 0.92rem; }
.tag { display:inline-block; border:1px solid #e5e5e5; padding:1px 8px; margin-right:6px;
       font-size:0.8rem; color:#404040; background:#fff; }
.score-card { border:1px solid #e5e5e5; background:#fff; padding:18px 22px; margin:6px 0 14px 0; }
.score-card b { font-size:1.6rem; }
.ev { font-size:0.92rem; color:#262626; margin:2px 0; }
.ev.bad { color:#DC2626; }
.legend li.bad { color:#DC2626; font-weight:600; }
footer { visibility: hidden; }
.st-key-legend button { min-height: 0; padding: 2px 0; text-align: left; justify-content: flex-start; }
.st-key-legend [data-testid="stVerticalBlock"] { gap: 0.15rem; }
</style>
""")


# ---------------------------------------------------------------- helpers
@st.cache_data(ttl=900, show_spinner=False, max_entries=200)
def run_store_check(url, with_speed, with_browser):
    results, notes, audit = analyze(url, with_speed, lambda msg: None, with_browser=with_browser)
    return results, notes, audit


def browser_ready():
    return core.browser_available() and bool(core.BROWSER_PATH or shutil.which("chrome"))


def with_priority(results):
    for r in results:
        r["ice"] = ice_score(r["id"], evidence_score(SOURCES, r["id"]))
    return sorted(results, key=lambda r: (r["passed"], -r["ice"][0]))


def summary(results):
    passed = sum(r["passed"] for r in results)
    ideas = len(results) - passed
    st.html(f"<div class='score-card'><b>{passed} of {len(results)}</b> checks passed"
            f"&nbsp;&nbsp;·&nbsp;&nbsp;<b>{ideas}</b> idea(s) to test"
            f"<div class='muted'>Ideas are ranked by ICE priority (impact, confidence, ease). "
            f"Open an item to see why it matters, what to try and how to fix it.</div></div>")


def bar_chart(r):
    data = r.get("chart") or []
    if not data:
        return
    df = pd.DataFrame([{"label": str(lbl)[:30], "value": v * 100,
                        "status": "needs attention" if flag else "ok"} for lbl, v, flag in data])
    chart = alt.Chart(df).mark_bar().encode(
        x=alt.X("value:Q", title="%"),
        y=alt.Y("label:N", sort=None, title=None),
        color=alt.Color("status:N", scale=alt.Scale(domain=["needs attention", "ok"],
                                                    range=["#0A0A0A", "#C7C7C7"]),
                        legend=alt.Legend(title=None, orient="bottom")),
        tooltip=[alt.Tooltip("label:N", title=""), alt.Tooltip("value:Q", format=".2f", title="%")],
    ).properties(title=r.get("chart_title", ""), height=alt.Step(38))
    st.altair_chart(chart, width="stretch")


def result_card(r, url, key):
    c = CHECKS[r["id"]]
    sc = r["ice"][0]
    status = ":red[**✗ Fix**]" if not r["passed"] else "✓ OK"
    prio = f"**{sc:.1f}**" if not r["passed"] else "—"
    label = f"{prio} &nbsp;·&nbsp; {c['title']} &nbsp;·&nbsp; {status} &nbsp;·&nbsp; _{r['page']}_"
    ev = evidence_items(SOURCES, r["id"])
    with st.expander(label):
        tabs = st.tabs(["Details", "Help me fix this", "UX/dev brief"] if not r["passed"] else ["Details"])
        with tabs[0]:
            meta = r["page"] + (f" · {r['detail']}" if r.get("detail") else "")
            if not r["passed"]:
                _, im, co, ea = r["ice"]
                meta += f" · Priority (ICE) {sc:.1f}/10 · Impact {im} · Confidence {co} · Ease {ea}"
            st.html(f"<div class='muted'>{meta}</div>")
            if r.get("chart"):
                bar_chart(r)
            st.markdown(f"**Why it matters**  \n{c['why']}")
            if r["id"] in CHECK_RULES:
                st.markdown(f"**How this was checked**  \n<span class='muted'>{CHECK_RULES[r['id']]}</span>",
                            unsafe_allow_html=True)
            if not r["passed"]:
                st.markdown(f"**What we found**  \nWe found {r['observation']}.")
                st.markdown(f"**What to try**  \nTry {c['change']}. The goal is to help visitors "
                            f"{c['action']}.")
                st.markdown(f"**Hypothesis (for an A/B test)**  \n{hypothesis(r)}")
            if ev:
                st.markdown("**Evidence** (research and case studies)")
                st.html("".join(f"<p class='ev{' bad' if i['effect'] != 'positive' else ''}'>• "
                                f"{_esc(evidence_line(i))}</p>" for i in ev))
            st.html("<p class='muted'>" + (
                "Thresholds are rules of thumb for spotting problems, not benchmarks."
                if r["page"] == "Your data" else
                "One store's result is a starting point for a hypothesis, not a guarantee.") + "</p>")
        if r["passed"]:
            return
        with tabs[1]:
            st.markdown(f"**Goal:** {c['change']}.")
            for i, s in enumerate(c["fix"], 1):
                st.markdown(f"{i}. {s}")
            if c.get("code"):
                st.markdown("**Code you can paste** (copy with the icon in the corner)")
                st.code(c["code"], language="liquid")
            st.markdown("**Ask an AI assistant**: paste this into Claude or any AI assistant for "
                        "steps that fit your theme.")
            st.code(ai_prompt(r, url), language=None, wrap_lines=True)
            st.markdown("**After the change**: check the page on mobile, then compare conversion and "
                        "revenue per visitor before and after (or run an A/B test if you have "
                        "enough traffic).")
        with tabs[2]:
            brief = make_brief(r, url, ev)
            st.download_button("Download brief (.md)", brief, file_name=f"brief_{r['id']}.md",
                               key=f"brief_{key}")
            st.markdown(brief)


def _esc(s):
    import html
    return html.escape(s)


def results_list(results, url, prefix):
    choice = st.radio("Show", ["All", "To fix", "OK"], horizontal=True, key=f"filter_{prefix}",
                      label_visibility="collapsed")
    shown = [r for r in results if choice == "All" or (choice == "To fix") != r["passed"]]
    if not shown:
        st.info("Nothing to show with this filter.")
    for i, r in enumerate(shown):
        result_card(r, url, f"{prefix}_{i}")


@st.cache_data(show_spinner=False, max_entries=20)
def screen_slices(shot, vh):
    """Cut the long screenshot into phone-screen-sized pieces."""
    from io import BytesIO
    from PIL import Image
    img = Image.open(shot)
    out = []
    for top in range(0, img.height, vh):
        part = img.crop((0, top, img.width, min(top + vh, img.height)))
        buf = BytesIO()
        part.save(buf, format="PNG")
        out.append(buf.getvalue())
    return out


@st.fragment
def visual_audit(audit):
    if not audit or not Path(audit.get("shot", "")).exists():
        return
    vh = int(audit.get("vh") or 844)
    slices = screen_slices(audit["shot"], vh)
    total = len(slices)
    key = f"screen_{audit['shot']}"
    i = min(st.session_state.get(key, 0), total - 1)

    st.subheader("Visual audit: the real mobile page")
    st.html("<p class='muted'>The product page opened as a phone (390×844), one screen at a time. "
            "Screen 1 is what a visitor sees without scrolling. Red circles: what should change. "
            "Pop-ups or cookie banners can cover parts of the page.</p>")
    left, right = st.columns([1, 1.4], gap="large")
    with left:
        st.image(slices[i], width=330)
        n1, n2, n3 = st.columns([1, 1.2, 1])
        if n1.button("◀", key=f"{key}_prev", disabled=i == 0, width="stretch"):
            st.session_state[key] = i - 1
            st.rerun(scope="fragment")
        n2.html(f"<p style='text-align:center;margin-top:8px'><b>{i + 1} / {total}</b></p>")
        if n3.button("▶", key=f"{key}_next", disabled=i == total - 1, width="stretch"):
            st.session_state[key] = i + 1
            st.rerun(scope="fragment")
        st.download_button("Download full screenshot", Path(audit["shot"]).read_bytes(),
                           file_name="mobile_audit.png", mime="image/png", key=f"{key}_dl",
                           width="stretch")
    with right, st.container(key="legend"):
        st.markdown("**What we measured** <span class='muted'>· click an item to jump to it</span>",
                    unsafe_allow_html=True)
        for it in audit["legend"]:
            if not it["n"]:
                continue
            screen = int((it.get("y") or 0) // vh)
            here = screen == i
            text = f"{it['n']}. {it['label']}: {it['status']}"
            text = f":red[{text}]" if it["bad"] else text
            if here:
                text = f"**{text}**  ← this screen"
            if st.button(text, key=f"{key}_go_{it['n']}_{it['key']}", type="tertiary"):
                st.session_state[key] = min(screen, total - 1)
                st.rerun(scope="fragment")
        missing = [it["label"] for it in audit["legend"] if not it["n"]]
        if missing:
            st.html(f"<p class='muted'>Not found on the page: {_esc(', '.join(missing))}</p>")
        if audit.get("cut"):
            st.html("<p class='muted'>Very long page: only the first 6,000 pixels are shown.</p>")



# ---------------------------------------------------------------- page
st.title("Shopify CRO Checker")
st.markdown("Find what stops shoppers from buying. A quick first-pass audit for Shopify stores, "
            "based on published research and case studies. "
            f"<span class='muted'>· [Source code on GitHub]({GITHUB})</span>", unsafe_allow_html=True)

tab_store, tab_data, tab_ab, tab_how, tab_src = st.tabs(
    ["Check a store", "Analytics data", "A/B test tools", "How it works", "Sources"])

# ---------- check a store
with tab_store:
    def clear_store():
        st.session_state.pop("store", None)
        st.session_state["url_in"] = ""

    with st.form("check"):
        url_in = st.text_input("Store or product link", key="url_in",
                               placeholder="e.g. yourstore.com or a product page link")
        c1, c2 = st.columns(2)
        with_speed = c1.checkbox("Google mobile speed test", help="Adds a mobile speed score. Takes up to a minute.")
        can_browse = browser_ready()
        with_browser = c2.checkbox(
            "Real mobile-browser audit", value=False, disabled=not can_browse,
            help=("Opens the product page as a phone, measures where key elements are and marks "
                  "them on a screenshot. Takes 20–40 seconds." if can_browse else
                  "Not available on this server. The desktop app has it."))
        b1, b2, _ = st.columns([1, 1, 6])
        go = b1.form_submit_button("Analyze", type="primary", width="stretch")
        b2.form_submit_button("Clear", on_click=clear_store, width="stretch")

    if go:
        if not url_in.strip():
            st.warning("Please paste a store or product link.")
        else:
            url = normalize(url_in)
            with st.spinner("Checking the store… this takes a few seconds"
                            + (" (longer with the extra options)" if with_speed or with_browser else "")):
                try:
                    if core.SAFE_MODE:
                        core.check_public(url)
                    results, notes, audit = run_store_check(url, with_speed, with_browser)
                    st.session_state["store"] = {"url": url, "results": with_priority([dict(r) for r in results]),
                                                 "notes": notes, "audit": audit}
                except core.BlockedURL as e:
                    st.session_state.pop("store", None)
                    st.error(str(e))
                except Exception as e:
                    st.session_state.pop("store", None)
                    st.error(f"The store could not be checked: {str(e).splitlines()[0][:200]}")

    res = st.session_state.get("store")
    if res:
        top_l, top_r = st.columns([3, 1])
        with top_l:
            summary(res["results"])
        with top_r:
            st.write("")
            st.download_button("Download report (HTML)",
                               html_report(res["url"], res["results"], res["notes"], res["audit"], SOURCES),
                               file_name="cro_report.html", mime="text/html", width="stretch")
        st.html(f"<p class='muted'>Checked: {_esc(res['url'])}</p>")
        visual_audit(res["audit"])
        results_list(res["results"], res["url"], "store")
        if res["notes"]:
            with st.expander("Notes about this check"):
                for n in res["notes"]:
                    st.markdown(f"- {n}")
    elif not go:
        st.html("<p class='muted'>The check reads the homepage and one product page, the way a "
                "visitor's browser would. Nothing is stored. Results are ideas to test, not "
                "verdicts.</p>")

# ---------- analytics data
with tab_data:
    st.markdown("Upload a CSV export from **Google Analytics 4** or **Shopify Analytics** to compare "
                "devices, channels and landing pages, and to see where carts and checkouts drop off.")
    with st.expander("How to export your data as CSV"):
        st.text(EXPORT_HELP)
    st.session_state.setdefault("up_key", 0)
    files = st.file_uploader("CSV files", type=["csv"], accept_multiple_files=True,
                             key=f"up_{st.session_state['up_key']}")
    samples = sorted((HERE / "samples").glob("*.csv"))
    if samples and not files:
        st.html("<p class='muted'>No data at hand? Try a sample file:</p>")
        names = {"sample_ga4_device": "Sample: GA4 by device", "sample_ga4_channels": "Sample: GA4 by channel"}
        cols = st.columns([1, 1, 3])
        for col, p in zip(cols, samples):
            if col.button(names.get(p.stem, p.stem), key=p.name):
                st.session_state["sample"] = str(p)
    paths = []
    if files:
        WORK_DIR.mkdir(parents=True, exist_ok=True)
        for f in files:
            p = WORK_DIR / f"upload_{abs(hash(f.file_id))}_{Path(f.name).name}"
            p.write_bytes(f.getvalue())
            paths.append(p)
        st.session_state.pop("sample", None)
    elif st.session_state.get("sample"):
        paths = [Path(st.session_state["sample"])]
    if paths:
        def clear_data():
            st.session_state.pop("sample", None)
            st.session_state["up_key"] += 1
        st.button("Clear", on_click=clear_data, key="clear_data")
        all_results, all_notes = [], []
        for p in paths:
            try:
                r_, n_ = analyze_data(p)
                all_results += r_
                all_notes += [n.replace(p.name, p.name.split("_", 2)[-1] if p.name.startswith("upload_") else p.name)
                              for n in n_]
            except Exception as e:
                st.error(f"{p.name.split('_', 2)[-1]}: {e}")
        if all_results:
            all_results = with_priority(all_results)
            summary(all_results)
            results_list(all_results, "your store", "data")
        for n in all_notes:
            st.html(f"<p class='muted'>{_esc(n)}</p>")

# ---------- A/B tools
with tab_ab:
    a, b = st.columns(2, gap="large")
    with a:
        st.subheader("Plan a test")
        st.html("<p class='muted'>How many visitors you need, and how long the test will run.</p>")
        weekly = st.number_input("Weekly visitors to the page", min_value=1, value=5000, step=500)
        base = st.number_input("Current conversion rate (%)", min_value=0.01, max_value=99.0, value=2.0, step=0.1)
        lift = st.number_input("Smallest uplift worth finding (%)", min_value=1.0, value=10.0, step=1.0,
                               help="Relative change, e.g. 10 means 2.0% → 2.2%")
        n = sample_size(base / 100, lift / 100)
        weeks = max(2.0, 2 * n / weekly)
        st.metric("Visitors needed per version", f"{n:,}")
        st.markdown(f"About **{weeks:.1f} weeks** with a 50/50 split ({2 * n:,} visitors in total).")
        st.html("<p class='muted'>95% significance, 80% power. Run at least two full weeks so every "
                "weekday is included. If it takes too long, test a bigger change or a busier page.</p>")
    with b:
        st.subheader("Read a result")
        st.html("<p class='muted'>Is the difference between A and B real or just chance?</p>")
        x1, x2 = st.columns(2)
        va = x1.number_input("A (original) visitors", min_value=1, value=4000)
        ca = x2.number_input("A purchases", min_value=0, value=80)
        vb = x1.number_input("B (variant) visitors", min_value=1, value=4000)
        cb = x2.number_input("B purchases", min_value=0, value=104)
        if ca > va or cb > vb:
            st.warning("Purchases can't be higher than visitors.")
        else:
            pa, pb, rel, p = ab_result(va, ca, vb, cb)
            m1, m2, m3 = st.columns(3)
            m1.metric("A", f"{pa * 100:.2f}%")
            m2.metric("B", f"{pb * 100:.2f}%", f"{rel * 100:+.1f}%")
            m3.metric("Confidence", f"{(1 - p) * 100:.1f}%")
            if p < 0.05 and rel > 0:
                st.success("B wins. The difference is very likely real.")
            elif p < 0.05 and rel < 0:
                st.error("B loses. Keep the original.")
            else:
                st.info("No clear winner yet. Keep the test running, or accept that the change makes "
                        "little difference.")
            st.html(f"<p class='muted'>Two-sided test at 95% (p = {p:.3f}). Also compare revenue per "
                    "visitor: a change can raise conversion but lower order value.</p>")

# ---------- how it works
with tab_how:
    st.subheader("How it works")
    steps = [
        ("1. Collect", "Loads the homepage and a product page (found through the store's public "
                       "product list or a homepage link), plus the product data Shopify publishes. "
                       "Optional: Google's speed test and a real mobile browser."),
        ("2. Check", f"Runs {len([k for k in CHECKS if not k.startswith('data_')])} simple, transparent "
                     "rules. Every result shows the exact rule it used under 'How this was checked'."),
        ("3. Explain and rank", "Says why each issue matters, writes a test hypothesis, shows the "
                                "research behind it and gives an ICE priority score."),
        ("4. Act", "Fix steps with code and an AI prompt, a UX/dev brief, A/B test tools and a "
                   "report you can share."),
    ]
    cols = st.columns(4)
    for col, (t, d) in zip(cols, steps):
        col.markdown(f"**{t}**")
        col.html(f"<p class='muted'>{d}</p>")
    st.markdown("**Priority (ICE)**")
    st.markdown("Each idea gets impact, confidence and ease scores from 1 to 10. Impact and ease "
                "come from the check itself. Confidence grows with the number of sources that "
                "support the idea and drops when a source contradicts it. The priority is the "
                "average of the three.")
    st.markdown("**Good to know**")
    st.markdown("- Rules read the page, they don't understand it. Some themes or apps can cause a "
                "false alarm, so treat results as ideas to test.\n"
                "- Built for Shopify stores. Other platforms only get the general checks.\n"
                "- Some stores block automated visits. Then the check can't read the page.\n"
                "- Nothing you enter is saved. Results are kept for a few minutes so a repeated "
                "check is faster.\n"
                f"- The [desktop version]({GITHUB}) also lets you add your own sources and read them "
                "with an optional AI add-on.")
    with st.expander("Glossary"):
        for term, meaning in GLOSSARY:
            st.markdown(f"**{term}**: {meaning}")

# ---------- sources
with tab_src:
    st.subheader("Sources")
    st.markdown("Studies and case studies that back up the ideas. They appear as evidence under "
                "the related checks and move well-supported ideas up the list. They don't change "
                "what is checked.")
    for s in SOURCES:
        n = len(s.get("checks", []))
        link = f" · [Open]({s['location']})" if s.get("location", "").startswith("http") else ""
        st.markdown(f"**{s['title']}**  \n{s.get('finding', '')}  \n"
                    f"<span class='muted'>{s.get('type', '')} · supports {n} check{'s' if n != 1 else ''}"
                    f"</span>{link}", unsafe_allow_html=True)
    st.html("<p class='muted'>Findings are short summaries in my own words, with a link to the "
            "original. All rights belong to their authors; this project is not affiliated with "
            "them.</p>")
    with st.expander("Check rules: what each check looks for"):
        for cid, rule in CHECK_RULES.items():
            st.markdown(f"**{CHECKS[cid]['title']}**: {rule}")

st.divider()
st.html(f"<p class='muted'>Built by Alper Kizik as a learning project · "
        f"<a href='{GITHUB}' target='_blank'>GitHub</a> · Results are ideas to test, not "
        f"guarantees.</p>")
