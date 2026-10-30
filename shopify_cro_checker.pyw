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

import os
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cro_core
from cro_core import *   # noqa: F401,F403  (check library, analysis, scoring, report)
from cro_core import _launch  # noqa: F401


# ---------------------------------------------------------------- colours / fonts
C = {
    "navy": "#0A0A0A", "navy2": "#262626", "bg": "#FAFAFA", "card": "#FFFFFF",
    "line": "#E5E5E5", "text": "#0A0A0A", "muted": "#737373", "accent": "#0A0A0A",
    "accent_dark": "#333333", "ok": "#737373", "ok_bg": "#F5F5F5", "bad": "#0A0A0A",
    "bad_bg": "#EDEDED", "hl": "#0A0A0A", "hl_bg": "#FFFFFF",
}
FONT = "Segoe UI" if sys.platform.startswith("win") else "Helvetica"
MARK = "#DC2626"   # the only colour: a pen-style circle around what should change



def save_sources(sources):
    err = cro_core.save_sources(sources)
    if err:
        messagebox.showerror(APP_NAME, f"Could not save sources:\n{err}")


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
    return cro_core.html_report(app.url, app.results, app.notes, getattr(app, "audit", None),
                                app.sources)


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
                msg = str(e)
                self.after(0, lambda: self._ai_fail(msg))
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
