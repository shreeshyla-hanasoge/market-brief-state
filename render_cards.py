#!/usr/bin/env python3
"""
render_cards.py — fixed multi-image template set for the Telegram market brief.

Usage:  python render_cards.py data.json /tmp/cards
Writes: 01_bias.png, 02_news.png, 03_chart_1.png (, 04_chart_2.png)

The routine agent must NOT design images. It only writes data.json in this
schema; this script owns 100% of the layout. Send all PNGs as ONE Telegram
album via sendMediaGroup.

data.json schema
----------------
{
  "title": "Intraday Market Brief",
  "timestamp": "14 Jul 2026 · 14:24 IST",
  "instruments": [                      # Bias Board rows, max 7
    { "name": "NIFTY 50", "price": "24,048.8", "chg_pct": -0.67,
      "news_bias": "bearish",           # bullish | bearish | neutral
      "tech_bias": "bearish",
      "tech_note": "Below VWAP · low 1/3 of range" }   # <= 38 chars
  ],
  "top_story": {
    "headline": "...",                  # <= 100 chars (wraps to 2 lines)
    "detail": "..."                     # <= 150 chars (wraps to 2 lines)
  },
  "news": [                             # max 5, post-dedup
    { "text": "...",                    # <= 115 chars (wraps to 2 lines)
      "source": "Business Standard",    # <= 22 chars
      "bias": "bearish",
      "tag": "HCLTECH" }                # <= 9 chars
  ],
  "charts": [                           # 1-2 chart cards, most newsworthy first
    {
      "title": "WTI CRUDE — INTRADAY",
      "prices": [...],                  # >= 20 points
      "vwap":   [...],                  # same length
      "stats": [                        # exactly 4 chips
        {"label": "LAST",  "value": "$80.55"},
        {"label": "Δ DAY", "value": "+3.08%"},
        {"label": "VWAP",  "value": "$80.23"},
        {"label": "RANGE", "value": "$77.86–81.13"}
      ],
      "levels": [                       # 2-4 horizontal S/R lines
        {"label": "Day High", "value": 81.13, "kind": "res"},   # res|sup|ref
        {"label": "Day Low",  "value": 77.86, "kind": "sup"}
      ],
      "zones": [                        # 0-2 shaded supply/demand bands
        {"label": "Demand", "lo": 79.40, "hi": 79.75, "kind": "demand"}
      ],                                # kind: demand | supply
      "note": "Above VWAP · buyers defended 79.4–79.75 twice"   # <= 90 chars
    }
  ],
  "sources": "Yahoo Finance, CNBC, Bloomberg"
}

Verdict logic is computed HERE (never by the agent):
  aligned bull -> green, aligned bear -> red, conflict -> amber CHOP,
  one-side neutral -> LEANS x, both neutral -> NEUTRAL.
"""

import json
import os
import sys
import textwrap

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["text.parse_math"] = False
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# ------------------------------------------------------------------ palette
BG    = "#0A0E14"
CARD  = "#131A28"
CARD2 = "#0D1320"
EDGE  = "#232E40"
TEXT  = "#EDF1F7"
MUTED = "#7E8A9C"
GREEN = "#2FBF71"
RED   = "#E5484D"
AMBER = "#E8A33D"
BLUE  = "#4C8DFF"
GRAY  = "#5F6A7A"

DPI = 200
BIAS_COLOR = {"bullish": GREEN, "bearish": RED, "neutral": GRAY}
BIAS_MARK  = {"bullish": "\u25B2", "bearish": "\u25BC", "neutral": "\u25CF"}
LVL_COLOR  = {"res": RED, "sup": GREEN, "ref": AMBER}
ZONE_COLOR = {"supply": RED, "demand": GREEN}

ML, MR = 0.055, 0.945          # shared page margins (all cards)


def verdict(news, tech):
    n, t = news.lower(), tech.lower()
    if n == t == "bullish":
        return "BULLISH · ALIGNED", GREEN, True
    if n == t == "bearish":
        return "BEARISH · ALIGNED", RED, True
    if {n, t} == {"bullish", "bearish"}:
        return "CONFLICT · CHOP", AMBER, True
    if n == t == "neutral":
        return "NEUTRAL", GRAY, False
    lean = n if n != "neutral" else t
    src = "NEWS-LED" if n != "neutral" else "TECH-LED"
    return (f"LEANS {'BULL' if lean == 'bullish' else 'BEAR'} · {src}",
            BIAS_COLOR[lean], False)


def new_card(w_in, h_in):
    fig = plt.figure(figsize=(w_in, h_in), dpi=DPI)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    return fig, ax, w_in / h_in


def panel(ax, aspect, x, y, w, h, fc=CARD, ec=EDGE, lw=1.2, r=0.012):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
        facecolor=fc, edgecolor=ec, linewidth=lw, mutation_aspect=aspect))


def chip(ax, aspect, x, y, w, h, label, color, filled, fs=11):
    fc = color if filled else CARD2
    tc = BG if filled else color
    panel(ax, aspect, x, y, w, h, fc=fc, ec=color, lw=1.4, r=0.010)
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
            fontsize=fs, fontweight="bold", color=tc)


def header(ax, title, sub, timestamp, title_y=0.966, sub_gap=0.040,
           title_fs=21):
    ax.text(ML, title_y, title, fontsize=title_fs, fontweight="bold",
            color=TEXT, va="top")
    ax.text(ML, title_y - sub_gap, sub, fontsize=10, fontweight="bold",
            color=BLUE, va="top")
    ax.text(MR, title_y - 0.004, timestamp, fontsize=10, color=MUTED,
            va="top", ha="right")


def footer(ax, sources):
    src = sources if len(sources) <= 52 else sources[:52].rstrip(", ") + "…"
    ax.plot([ML, MR], [0.055, 0.055], color=EDGE, lw=1)
    ax.text(ML, 0.040, f"Sources: {src}", fontsize=8, color=MUTED, va="top")
    ax.text(MR, 0.040, "News summary · Not investment advice", fontsize=8,
            color=MUTED, va="top", ha="right", style="italic")


# =================================================================== CARD 1
def bias_card(data, path):
    fig, ax, asp = new_card(7.2, 9.0)               # 1440 x 1800
    header(ax, "Bias Board", "NEWS  vs  TECHNICALS", data["timestamp"])

    rows = data["instruments"][:7]
    top, bot, gap = 0.892, 0.118, 0.014
    row_h = (top - bot - gap * (len(rows) - 1)) / len(rows)

    for i, inst in enumerate(rows):
        y = top - (i + 1) * row_h - i * gap
        panel(ax, asp, ML, y, MR - ML, row_h)
        ax.text(0.085, y + row_h * 0.72, inst["name"], fontsize=14.5,
                fontweight="bold", color=TEXT, va="center")
        ax.text(0.085, y + row_h * 0.24, inst.get("tech_note", "")[:38],
                fontsize=8.5, color=MUTED, va="center")
        ax.text(0.475, y + row_h * 0.72, inst["price"], fontsize=14,
                color=TEXT, va="center", ha="right")
        chg = inst["chg_pct"]
        cc = GREEN if chg > 0 else RED if chg < 0 else GRAY
        ax.text(0.475, y + row_h * 0.28, f"{chg:+.2f}%", fontsize=11.5,
                fontweight="bold", color=cc, va="center", ha="right")
        nb, tb = inst["news_bias"].lower(), inst["tech_bias"].lower()
        ax.text(0.535, y + row_h * 0.72, f"NEWS {BIAS_MARK[nb]}",
                fontsize=9.5, fontweight="bold", color=BIAS_COLOR[nb],
                va="center")
        ax.text(0.690, y + row_h * 0.72, f"TECH {BIAS_MARK[tb]}",
                fontsize=9.5, fontweight="bold", color=BIAS_COLOR[tb],
                va="center")
        vl, vc, vf = verdict(nb, tb)
        chip(ax, asp, 0.530, y + row_h * 0.14, 0.385, row_h * 0.36,
             vl, vc, vf, fs=9.5)

    ax.text(ML, 0.098,
            "ALIGNED = news & technicals agree (conviction)   ·   "
            "CONFLICT = disagreement (chop / fade risk)",
            fontsize=8.5, color=MUTED, va="top")
    footer(ax, data["sources"])
    fig.savefig(path, facecolor=BG)
    plt.close(fig)


# =================================================================== CARD 2
def news_card(data, path):
    fig, ax, asp = new_card(7.2, 9.0)               # 1440 x 1800
    header(ax, "News", "NEW SINCE LAST BRIEF · DEDUPED", data["timestamp"])

    # ---- top story hero (height adapts to wrapped line count)
    ts = data["top_story"]
    hl = textwrap.wrap(ts["headline"], 46)[:2]
    dl = textwrap.wrap(ts["detail"], 74)[:2]
    pad_t, lab_h, hl_lh, dl_lh, pad_b = 0.020, 0.026, 0.034, 0.025, 0.018
    hero_h = pad_t + lab_h + len(hl) * hl_lh + len(dl) * dl_lh + pad_b
    hy = 0.885 - hero_h
    panel(ax, asp, ML, hy, MR - ML, hero_h, fc=CARD2, ec=BLUE, lw=1.6)
    ax.add_patch(FancyBboxPatch((ML, hy), 0.009, hero_h,
                 boxstyle="round,pad=0,rounding_size=0.004",
                 facecolor=BLUE, edgecolor="none", mutation_aspect=asp))
    cy = hy + hero_h - pad_t
    ax.text(0.090, cy, "TOP STORY", fontsize=9.5, fontweight="bold",
            color=BLUE, va="top")
    cy -= lab_h
    for line in hl:
        ax.text(0.090, cy, line, fontsize=14.5, fontweight="bold",
                color=TEXT, va="top")
        cy -= hl_lh
    for line in dl:
        ax.text(0.090, cy, line, fontsize=9.5, color=MUTED, va="top")
        cy -= dl_lh

    # ---- news items, evenly spaced in the remaining band
    items = data["news"][:5]
    top, bot, gap = hy - 0.026, 0.115, 0.013
    n = max(len(items), 1)
    item_h = (top - bot - gap * (n - 1)) / n
    for i, it in enumerate(items):
        iy = top - (i + 1) * item_h - i * gap
        b = it["bias"].lower()
        panel(ax, asp, ML, iy, MR - ML, item_h)
        ax.add_patch(FancyBboxPatch((ML, iy), 0.009, item_h,
                     boxstyle="round,pad=0,rounding_size=0.004",
                     facecolor=BIAS_COLOR[b], edgecolor="none",
                     mutation_aspect=asp))
        # tag pill, vertically centered on the right
        tag = it["tag"][:9].upper()
        tw = 0.020 + 0.0115 * len(tag)
        chip(ax, asp, MR - 0.028 - tw, iy + item_h * 0.5 - 0.014,
             tw, 0.028, tag, BIAS_COLOR[b], False, fs=8.5)
        # text wrapped clear of the pill column
        lines = textwrap.wrap(it["text"], 54)[:2]
        ty = iy + item_h - 0.022
        for line in lines:
            ax.text(0.090, ty, line, fontsize=11.5, color=TEXT, va="top")
            ty -= 0.027
        ax.text(0.090, iy + 0.016, f"\u2014 {it['source'][:22]}",
                fontsize=8.5, color=MUTED, va="bottom")

    footer(ax, data["sources"])
    fig.savefig(path, facecolor=BG)
    plt.close(fig)


# =================================================================== CARD 3+
def chart_card(chart, data, path):
    fig, ax, asp = new_card(7.2, 6.0)               # 1440 x 1200
    header(ax, chart["title"].upper(), "PRICE · VWAP · KEY LEVELS",
           data["timestamp"], title_y=0.952, sub_gap=0.055, title_fs=17)

    # ---- stat chips, flush with panel edges
    stats = chart.get("stats", [])[:4]
    if stats:
        g = 0.018
        cw = (MR - ML - g * 3) / 4
        sy, sh = 0.760, 0.088
        for i, s in enumerate(stats):
            sx = ML + i * (cw + g)
            panel(ax, asp, sx, sy, cw, sh, fc=CARD2)
            ax.text(sx + cw / 2, sy + sh * 0.70, s["label"], fontsize=8,
                    fontweight="bold", color=MUTED, ha="center", va="center")
            ax.text(sx + cw / 2, sy + sh * 0.30, s["value"][:14],
                    fontsize=10.5, fontweight="bold", color=TEXT,
                    ha="center", va="center")

    # ---- chart panel
    py, ph = 0.185, 0.545
    panel(ax, asp, ML, py, MR - ML, ph)
    cax = fig.add_axes([0.125, py + 0.060, 0.68, ph - 0.105])
    cax.set_facecolor(CARD)

    prices, vwap = chart["prices"], chart["vwap"]
    levels = chart.get("levels", [])[:4]
    zones = chart.get("zones", [])[:2]
    xs = list(range(len(prices)))
    last = prices[-1]
    up = last >= vwap[-1]
    line_c = GREEN if up else RED

    # y-limits include levels & zones with padding
    ys = list(prices) + list(vwap) + [l["value"] for l in levels]
    for z in zones:
        ys += [z["lo"], z["hi"]]
    lo, hi = min(ys), max(ys)
    pad = (hi - lo) * 0.08 or 1
    cax.set_ylim(lo - pad, hi + pad)
    cax.set_xlim(0, len(xs) - 1)

    for z in zones:
        zc = ZONE_COLOR[z["kind"].lower()]
        cax.axhspan(z["lo"], z["hi"], color=zc, alpha=0.10, zorder=1)
        cax.text(0.5, (z["lo"] + z["hi"]) / 2,
                 f" {z['label'].upper()} ", fontsize=7, fontweight="bold",
                 color=zc, va="center", zorder=2)
    for lv in levels:
        lc = LVL_COLOR[lv["kind"].lower()]
        cax.axhline(lv["value"], color=lc, lw=1.1, ls=":", alpha=0.95,
                    zorder=2)
        cax.annotate(f"{lv['label']}  {lv['value']:g}",
                     xy=(len(xs) - 1, lv["value"]),
                     xytext=(4, 0), textcoords="offset points",
                     fontsize=7, fontweight="bold", color=lc,
                     va="center", ha="left", annotation_clip=False)

    cax.plot(xs, prices, color=line_c, lw=2.2, zorder=4, label="Price")
    cax.fill_between(xs, prices, cax.get_ylim()[0], color=line_c,
                     alpha=0.08, zorder=1)
    cax.plot(xs, vwap, color=AMBER, lw=1.6, ls="--", zorder=3, label="VWAP")
    # last-price marker
    cax.scatter([xs[-1]], [last], s=26, color=line_c, zorder=5)
    cax.annotate(f"{last:g}", xy=(xs[-1], last), xytext=(6, 10),
                 textcoords="offset points", fontsize=8.5,
                 fontweight="bold", color=BG, annotation_clip=False,
                 bbox=dict(boxstyle="round,pad=0.28", fc=line_c, ec="none"))

    cax.legend(loc="upper left", fontsize=8, frameon=False, labelcolor=MUTED)
    for s in cax.spines.values():
        s.set_color(EDGE)
    cax.tick_params(colors=MUTED, labelsize=7.5)
    cax.set_xticks([])
    cax.grid(color=EDGE, lw=0.5, alpha=0.55)

    ax.text(ML, 0.150, chart["note"][:90], fontsize=10, color=MUTED,
            va="top")
    footer(ax, data["sources"])
    fig.savefig(path, facecolor=BG)
    plt.close(fig)


def main():
    data = json.load(open(sys.argv[1]))
    outdir = sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    made = []
    p = os.path.join(outdir, "01_bias.png"); bias_card(data, p); made.append(p)
    p = os.path.join(outdir, "02_news.png"); news_card(data, p); made.append(p)
    for i, ch in enumerate(data.get("charts", [])[:2], 1):
        p = os.path.join(outdir, f"{i + 2:02d}_chart_{i}.png")
        chart_card(ch, data, p); made.append(p)
    print("\n".join(made))


if __name__ == "__main__":
    main()
