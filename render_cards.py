#!/usr/bin/env python3
"""
render_cards.py — fixed multi-image template set for the Telegram market brief.

Usage:  python render_cards.py data.json /tmp/cards
Writes: /tmp/cards/01_bias.png, /tmp/cards/02_news.png,
        /tmp/cards/03_chart_1.png, 04_chart_2.png ... (one per charts[] entry)

The routine agent must NOT design images. It only writes data.json in this
schema; this script owns 100% of the layout. Cards are 1440px wide @2x for
crisp mobile rendering. Send them as ONE Telegram album via sendMediaGroup.

data.json schema
----------------
{
  "title": "Intraday Market Brief",
  "timestamp": "14 Jul 2026 · 14:24 IST",
  "instruments": [                      # Bias Board rows, max 6
    {
      "name": "NIFTY 50",
      "price": "24,048.8",
      "chg_pct": -0.67,                 # signed float
      "news_bias": "bearish",           # bullish | bearish | neutral
      "tech_bias": "bearish",
      "tech_note": "Below VWAP · low 1/3 of range"     # <= 38 chars
    }, ...
  ],
  "top_story": {
    "headline": "...",                  # <= 110 chars (wraps to 2 lines)
    "detail": "..."                     # <= 130 chars (wraps to 2 lines)
  },
  "news": [                             # max 5, post-dedup
    { "text": "...",                    # <= 120 chars (wraps to 2 lines)
      "source": "Business Standard",
      "bias": "bearish",
      "tag": "HCLTECH" }                # <= 10 chars
  ],
  "charts": [                           # 1-2 chart cards, most newsworthy first
    {
      "title": "WTI CRUDE — INTRADAY",
      "prices": [...],                  # >= 20 points
      "vwap":   [...],                  # same length
      "stats": [                        # exactly 4 stat chips
        {"label": "LAST",  "value": "$80.55"},
        {"label": "Δ DAY", "value": "+3.08%"},
        {"label": "VWAP",  "value": "$80.23"},
        {"label": "RANGE", "value": "$77.86–81.13"}
      ],
      "note": "Above VWAP · 82% up the day's range"    # <= 80 chars
    }
  ],
  "sources": "Yahoo Finance, CNBC, Bloomberg"
}
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


def header(ax, title, sub, timestamp):
    ax.text(0.055, 0.968, title, fontsize=21, fontweight="bold",
            color=TEXT, va="top")
    ax.text(0.055, 0.933, sub, fontsize=10.5, fontweight="bold",
            color=BLUE, va="top")
    ax.text(0.945, 0.964, timestamp, fontsize=10, color=MUTED,
            va="top", ha="right")


def footer(ax, left, right="News summary. Not investment advice."):
    ax.plot([0.055, 0.945], [0.052, 0.052], color=EDGE, lw=1)
    ax.text(0.055, 0.038, left, fontsize=8, color=MUTED, va="top")
    ax.text(0.945, 0.038, right, fontsize=8, color=MUTED, va="top",
            ha="right", style="italic")


# =================================================================== CARD 1
def bias_card(data, path):
    fig, ax, asp = new_card(7.2, 9.0)               # 1440 x 1800
    header(ax, "Bias Board", "NEWS  vs  TECHNICALS", data["timestamp"])

    rows = data["instruments"][:6]
    top, bot = 0.895, 0.105
    gap = 0.014
    row_h = (top - bot - gap * (len(rows) - 1)) / len(rows)

    for i, inst in enumerate(rows):
        y = top - (i + 1) * row_h - i * gap
        panel(ax, asp, 0.055, y, 0.89, row_h)
        # left block: name / note
        ax.text(0.085, y + row_h * 0.72, inst["name"], fontsize=14.5,
                fontweight="bold", color=TEXT, va="center")
        ax.text(0.085, y + row_h * 0.24, inst.get("tech_note", "")[:38],
                fontsize=8.5, color=MUTED, va="center")
        # middle block: price / change
        ax.text(0.475, y + row_h * 0.72, inst["price"], fontsize=14,
                color=TEXT, va="center", ha="right")
        chg = inst["chg_pct"]
        cc = GREEN if chg > 0 else RED if chg < 0 else GRAY
        ax.text(0.475, y + row_h * 0.28, f"{chg:+.2f}%", fontsize=11.5,
                fontweight="bold", color=cc, va="center", ha="right")
        # right block: news/tech minis over verdict chip
        nb, tb = inst["news_bias"].lower(), inst["tech_bias"].lower()
        ax.text(0.535, y + row_h * 0.72,
                f"NEWS {BIAS_MARK[nb]}", fontsize=9.5, fontweight="bold",
                color=BIAS_COLOR[nb], va="center")
        ax.text(0.685, y + row_h * 0.72,
                f"TECH {BIAS_MARK[tb]}", fontsize=9.5, fontweight="bold",
                color=BIAS_COLOR[tb], va="center")
        vl, vc, vf = verdict(nb, tb)
        chip(ax, asp, 0.530, y + row_h * 0.14, 0.385, row_h * 0.36,
             vl, vc, vf, fs=9.5)

    ax.text(0.055, 0.085,
            "ALIGNED = news & technicals agree (conviction)   ·   "
            "CONFLICT = disagreement (chop / fade risk)",
            fontsize=8.5, color=MUTED, va="top")
    footer(ax, f"Sources: {data['sources'][:70]}")
    fig.savefig(path, facecolor=BG)
    plt.close(fig)


# =================================================================== CARD 2
def news_card(data, path):
    fig, ax, asp = new_card(7.2, 9.0)               # 1440 x 1800
    header(ax, "News", "NEW SINCE LAST BRIEF — DEDUPED", data["timestamp"])

    # top story hero
    ts = data["top_story"]
    hero_h = 0.155
    y = 0.895 - hero_h
    panel(ax, asp, 0.055, y, 0.89, hero_h, fc=CARD2, ec=BLUE, lw=1.6)
    ax.text(0.085, y + hero_h - 0.022, "TOP STORY", fontsize=10,
            fontweight="bold", color=BLUE, va="top")
    hl = textwrap.wrap(ts["headline"], 52)[:2]
    for j, line in enumerate(hl):
        ax.text(0.085, y + hero_h - 0.052 - j * 0.032, line, fontsize=14.5,
                fontweight="bold", color=TEXT, va="top")
    dt = textwrap.wrap(ts["detail"], 74)[:2]
    for j, line in enumerate(dt):
        ax.text(0.085, y + hero_h - 0.052 - len(hl) * 0.032 - j * 0.024,
                line, fontsize=10, color=MUTED, va="top")

    # news items
    items = data["news"][:5]
    top = y - 0.030
    item_h = (top - 0.105) / 5 - 0.012
    for i, it in enumerate(items):
        iy = top - (i + 1) * item_h - i * 0.012
        b = it["bias"].lower()
        panel(ax, asp, 0.055, iy, 0.89, item_h)
        ax.add_patch(FancyBboxPatch(
            (0.055, iy), 0.008, item_h,
            boxstyle="round,pad=0,rounding_size=0.004",
            facecolor=BIAS_COLOR[b], edgecolor="none", mutation_aspect=asp))
        lines = textwrap.wrap(it["text"], 62)[:2]
        for j, line in enumerate(lines):
            ax.text(0.085, iy + item_h * (0.74 - j * 0.28), line,
                    fontsize=11.5, color=TEXT, va="center")
        ax.text(0.085, iy + item_h * 0.16, f"— {it['source']}",
                fontsize=8.5, color=MUTED, va="center")
        ax.text(0.918, iy + item_h * 0.5, it["tag"][:10].upper(),
                fontsize=10, fontweight="bold", color=BIAS_COLOR[b],
                va="center", ha="right")

    footer(ax, f"Sources: {data['sources'][:70]}")
    fig.savefig(path, facecolor=BG)
    plt.close(fig)


# =================================================================== CARD 3+
def chart_card(chart, data, path):
    fig, ax, asp = new_card(7.2, 5.4)               # 1440 x 1080
    header(ax, chart["title"].title(), "INTRADAY · VWAP OVERLAY",
           data["timestamp"])

    # stat chips
    stats = chart.get("stats", [])[:4]
    if stats:
        cw, sy, sh = 0.2075, 0.775, 0.075
        for i, s in enumerate(stats):
            sx = 0.055 + i * (cw + 0.020)
            panel(ax, asp, sx, sy, cw, sh, fc=CARD2)
            ax.text(sx + cw / 2, sy + sh * 0.68, s["label"], fontsize=8,
                    fontweight="bold", color=MUTED, ha="center", va="center")
            ax.text(sx + cw / 2, sy + sh * 0.30, s["value"], fontsize=10.5,
                    fontweight="bold", color=TEXT, ha="center", va="center")

    # chart panel
    py, ph = 0.165, 0.565
    panel(ax, asp, 0.055, py, 0.89, ph)
    cax = fig.add_axes([0.115, py + 0.055, 0.79, ph - 0.10])
    cax.set_facecolor(CARD)
    prices, vwap = chart["prices"], chart["vwap"]
    xs = range(len(prices))
    up = prices[-1] >= vwap[-1]
    line_c = GREEN if up else RED
    cax.plot(xs, prices, color=line_c, lw=2.2, label="Price", zorder=3)
    cax.fill_between(xs, prices, min(prices), color=line_c, alpha=0.10)
    cax.plot(xs, vwap, color=AMBER, lw=1.6, ls="--", label="VWAP", zorder=2)
    cax.legend(loc="upper left", fontsize=8.5, frameon=False,
               labelcolor=MUTED)
    for s in cax.spines.values():
        s.set_color(EDGE)
    cax.tick_params(colors=MUTED, labelsize=8)
    cax.set_xticks([])
    cax.grid(color=EDGE, lw=0.5, alpha=0.6)

    ax.text(0.055, 0.135, chart["note"][:80], fontsize=10.5, color=MUTED,
            va="top")
    footer(ax, f"Sources: {data['sources'][:70]}")
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
