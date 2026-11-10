#!/usr/bin/env python3
"""
Render the GitHub profile README as a stack of animated SVG cards.

Design follows the animated-SVG-card pattern: every visual lives inside a
self-contained SVG shown through an <img> tag (GitHub strips scripts and
external CSS from READMEs, but an SVG's own <style> block and SMIL
animations run). Cards are drawn from real contribution data — the public
contribution calendar — refreshed daily by .github/workflows/cards.yml.

Usage:
    python scripts/render_readme_cards.py            # render from data/contributions.json
    python scripts/render_readme_cards.py --fetch    # refresh the JSON first, then render
    STATIC=1 python scripts/render_readme_cards.py   # final-frame render (for screenshots)

Only the Python standard library is used, so CI needs no installs.
"""
import base64
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USERNAME = "Manoj-2424150118"
STATIC = os.environ.get("STATIC") == "1"

# ---------------------------------------------------------------- data layer

def fetch_calendar():
    """Fetch the public contribution calendar (per-year fragments, stitched).

    Returns a list of (date, count) for the rolling last 366 days, today last.
    This is exactly what a visitor's browser sees on the profile — public
    contributions only.
    """
    today = dt.date.today()
    start = today - dt.timedelta(days=365)
    days = {}
    for year in range(start.year, today.year + 1):
        url = (f"https://github.com/users/{USERNAME}/contributions"
               f"?from={year}-01-01&to={year}-12-31")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        doc = None
        for attempt in range(3):
            try:
                doc = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
                break
            except Exception:
                if attempt == 2:
                    raise
                import time
                time.sleep(5 * (attempt + 1))
        dates = re.findall(r'data-date="(\d{4}-\d{2}-\d{2})"', doc)
        tips = re.findall(r"<tool-tip[^>]*>([^<]+)</tool-tip>", doc)
        for date_s, tip in zip(dates, tips):
            tip = html.unescape(tip).strip()
            count = 0 if tip.startswith("No contributions") else int(re.match(r"(\d+)", tip).group(1))
            days[date_s] = count
    out = []
    day = start
    while day <= today:
        out.append((day.isoformat(), days.get(day.isoformat(), 0)))
        day += dt.timedelta(days=1)
    return out


def load_days():
    path = os.path.join(ROOT, "data", "contributions.json")
    with open(path) as f:
        return [tuple(x) for x in json.load(f)["days"]]


def save_days(days):
    path = os.path.join(ROOT, "data", "contributions.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"days": days}, f)


def stats(days):
    total = sum(c for _, c in days)
    active = sum(1 for _, c in days if c > 0)
    busiest = max(days, key=lambda x: x[1])
    streak = 0
    for i, (date_s, c) in enumerate(reversed(days)):
        if c > 0:
            streak += 1
        elif i == 0:
            continue  # today is not over yet
        else:
            break
    months = []
    seen = []
    for date_s, c in days:
        key = date_s[:7]
        if key not in seen:
            seen.append(key)
            months.append([key, 0])
        months[-1][1] += c
    return {"total": total, "active": active, "busiest": busiest,
            "streak": streak, "months": months[-12:]}

# ---------------------------------------------------------------- svg helpers

THEMES = {
    "light": {
        "BG": "#f6f3ec", "PANEL": "#efe9dc", "BORDER": "#ddd5c2",
        "INK": "#171512", "INK_SOFT": "#3d3a33", "PORTRAIT_INK": "#33302a",
        "DIM": "#55534a", "FAINT": "#8a8578",
        "SKY": "#2e56e8", "SKY_LT": "#7d9bff", "DEEP": "#1d3fa8",
        "GREEN": "#1a7f37", "AMBER": "#e3a008", "RED": "#e2483d",
        "HEAT0": "#e9e4d6", "HEAT1": "#ccd8fc", "HEAT2": "#8aa5f8",
        "BAR_INK": "#2b2925", "PURPLE": "#a371f7", "TEAL": "#0e7c86",
    },
    "dark": {
        "BG": "#0d1117", "PANEL": "#161b22", "BORDER": "#2c3646",
        "INK": "#e6edf3", "INK_SOFT": "#c3ccd6", "PORTRAIT_INK": "#b9cbdd",
        "DIM": "#9aa7b4", "FAINT": "#6e7a88",
        "SKY": "#5b83f5", "SKY_LT": "#a9c2ff", "DEEP": "#7d9bff",
        "GREEN": "#3fb950", "AMBER": "#eab308", "RED": "#f0665e",
        "HEAT0": "#1c2330", "HEAT1": "#173a75", "HEAT2": "#1f5fd0",
        "BAR_INK": "#d7dee8", "PURPLE": "#bc8cff", "TEAL": "#39c5cf",
    },
}


def apply_theme(name):
    globals().update(THEMES[name])


apply_theme("light")

FONT_CSS = ""


def font_face():
    global FONT_CSS
    if FONT_CSS:
        return FONT_CSS
    faces = []
    for fname, style in (("serif-sub.woff", "normal"), ("serif-italic-sub.woff", "italic")):
        path = os.path.join(ROOT, "scripts", "fonts", fname)
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        faces.append("@font-face{font-family:'Instrument Serif';font-style:" + style + ";"
                     f"src:url(data:font/woff;base64,{b64}) format('woff');}}")
    FONT_CSS = "".join(faces)
    return FONT_CSS


BASE_CSS = """
.rise{opacity:0;animation:rise .8s cubic-bezier(.2,.7,.3,1) forwards}
@keyframes rise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
.pop{opacity:0;transform-box:fill-box;transform-origin:center;animation:pop .45s ease-out forwards}
@keyframes pop{0%{opacity:0;transform:scale(0)}70%{opacity:1;transform:scale(1.25)}100%{opacity:1;transform:scale(1)}}
.grow{transform-box:fill-box;transform-origin:bottom;animation:grow .7s cubic-bezier(.2,.7,.3,1) forwards;transform:scaleY(0)}
@keyframes grow{to{transform:scaleY(1)}}
.fade{opacity:0;animation:fadein .9s ease-out forwards}
@keyframes fadein{to{opacity:1}}
.pulse{animation:pulse 2.2s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}
.ring{transform-box:fill-box;transform-origin:center;animation:ring 3.2s ease-out infinite;opacity:0}
@keyframes ring{0%{opacity:.7;transform:scale(.3)}70%{opacity:0;transform:scale(1.9)}100%{opacity:0;transform:scale(1.9)}}
.nudge{animation:nudge 2.6s ease-in-out infinite}
@keyframes nudge{0%,100%{transform:translateX(0)}50%{transform:translateX(5px)}}
.swing{opacity:0;transform-box:fill-box;transform-origin:50% 100%;animation:swing .9s cubic-bezier(.2,.7,.3,1.2) forwards}
@keyframes swing{0%{opacity:0;transform:translateY(52px) rotate(2.6deg)}60%{opacity:1;transform:translateY(-7px) rotate(-.7deg)}100%{opacity:1;transform:translateY(0) rotate(0deg)}}
.static *{animation:none!important}
.static .rise,.static .fade,.static .pop,.static .grow,.static .swing{opacity:1!important;transform:none!important}
@media (prefers-reduced-motion: reduce){*{animation:none!important}}
"""

SERIF = "font-family:'Instrument Serif',Georgia,serif"
SANS = "font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
MONO = "font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace"


def svg_open(w, h, with_font=False):
    css = BASE_CSS + (font_face() if with_font else "")
    cls = ' class="static"' if STATIC else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}"{cls}>\n<style>{css}</style>\n'
            f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="12" fill="{BG}" stroke="{BORDER}"/>\n')


def svg_close():
    return "</svg>\n"


def esc(s):
    return html.escape(s, quote=True)


def shine_gradient(gid, base, hi):
    """A base fill with a light band that sweeps across via SMIL."""
    if STATIC:
        return (f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="0">'
                f'<stop offset="0" stop-color="{base}"/><stop offset="1" stop-color="{base}"/>'
                f'</linearGradient>')
    return (f'<linearGradient id="{gid}" x1="-0.6" y1="0" x2="0" y2="0">'
            f'<stop offset="0" stop-color="{base}"/><stop offset="0.45" stop-color="{base}"/>'
            f'<stop offset="0.5" stop-color="{hi}"/><stop offset="0.55" stop-color="{base}"/>'
            f'<stop offset="1" stop-color="{base}"/>'
            f'<animateTransform attributeName="gradientTransform" type="translate" '
            f'values="0 0; 2.2 0" dur="5s" begin="2.4s" repeatCount="indefinite"/>'
            f'</linearGradient>')


def count_up(x, y, target, color, size, delay, anchor="middle", frames=14):
    """SMIL count-up: stacked <text> values, each shown briefly (CSS can't change text)."""
    if STATIC or target == 0:
        return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" '
                f'fill="{color}" style="{SERIF}">{target}</text>')
    vals = []
    for i in range(1, frames + 1):
        t = i / frames
        vals.append(round(target * (1 - (1 - t) ** 2)))
    vals[-1] = target
    step = 0.055
    parts = []
    for i, v in enumerate(vals):
        begin = delay + i * step
        if i < len(vals) - 1:
            vis = (f'<set attributeName="visibility" to="visible" begin="{begin:.2f}s"/>'
                   f'<set attributeName="visibility" to="hidden" begin="{begin + step:.2f}s"/>')
        else:
            vis = f'<set attributeName="visibility" to="visible" begin="{begin:.2f}s" fill="freeze"/>'
        parts.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" '
                     f'fill="{color}" style="{SERIF}" visibility="hidden">{v}{vis}</text>')
    return "".join(parts)

# ---------------------------------------------------------------- cards

def hero():
    w, h = 880, 516
    s = [svg_open(w, h, with_font=True)]
    s.append('<defs>' + shine_gradient("shine", INK, SKY_LT) + '</defs>')
    # kicker: pulsing periwinkle square + mono role line (reference: role at org)
    s.append(f'<rect x="54" y="45" width="13" height="13" rx="3.5" fill="#a3b8f8" class="pulse"/>')
    s.append(f'<text x="78" y="57" font-size="13" letter-spacing="3" fill="{DIM}" '
             f'style="{MONO};animation-delay:0.05s" class="fade">AI FELLOW AT HANDSHAKE AI</text>')
    s.append(f'<text x="52" y="208" font-size="96" fill="{INK}" style="{SERIF};animation-delay:0.15s" '
             f'class="rise">Manoj Kumar</text>')
    s.append(f'<text x="52" y="314" font-size="96" fill="url(#shine)" font-style="italic" '
             f'style="{SERIF};animation-delay:0.35s" class="rise">Sharma</text>')
    s.append(f'<text x="54" y="374" font-size="19.5" fill="{INK_SOFT}" style="{SANS};animation-delay:0.6s" '
             f'class="rise">I build tools that check links, emails</text>')
    s.append(f'<text x="54" y="402" font-size="19.5" fill="{INK_SOFT}" style="{SANS};animation-delay:0.7s" '
             f'class="rise">and files, and teach people to spot scams.</text>')
    s.append(f'<text x="54" y="454" font-size="15" fill="{INK}" style="{MONO};animation-delay:0.9s" '
             f'class="fade">manoj-2424150118.github.io<tspan fill="{SKY}"> ↗</tspan></text>')
    # ASCII portrait (from his photo; data in scripts/portrait.txt) — 96 rows,
    # printing in row by row like a slow terminal, 18 ms per row (reference design).
    ppath = os.path.join(ROOT, "scripts", "portrait.txt")
    if os.path.exists(ppath):
        with open(ppath) as f:
            rows = [ln.rstrip("\n") for ln in f]
        for i, row in enumerate(rows):
            if not row.strip():
                row = " "  # blank rows still print (a beat in the terminal rhythm)
            delay = 0.55 + i * 0.018
            if STATIC:
                st = MONO
                cls = ""
            else:
                st = f"{MONO};animation-delay:{delay:.2f}s"
                cls = ' class="fade"'
            s.append(f'<text x="492" y="{30 + i * 4.9:.0f}" font-size="5.6" fill="{PORTRAIT_INK}" '
                     f'style="{st}" xml:space="preserve"{cls}>{esc(row)}</text>')
    return "".join(s) + svg_close()


def heatmap(days):
    w, h = 880, 200
    s = [svg_open(w, h)]
    st = stats(days)
    s.append(f'<text x="40" y="36" font-size="12.5" letter-spacing="2.5" fill="{FAINT}" style="{MONO}">CONTRIBUTIONS</text>')
    s.append(f'<text x="840" y="36" text-anchor="end" font-size="12.5" fill="{DIM}" style="{MONO}">last 52 weeks · {st["total"]} total</text>')
    # grid: align to full weeks (Sun..Sat), most recent 53 columns
    by_date = dict(days)
    today = dt.date.fromisoformat(days[-1][0])
    last_sat = today + dt.timedelta(days=(5 - today.weekday() + 7) % 7) if False else today + dt.timedelta(days=(5 - (today.weekday())) % 7)
    # python weekday: Mon=0..Sun=6; GitHub weeks start Sunday. Compute Sunday-start columns.
    def sunday_of(d):
        return d - dt.timedelta(days=(d.weekday() + 1) % 7)
    end_sunday = sunday_of(today)
    cols = 53
    start_sunday = end_sunday - dt.timedelta(weeks=cols - 1)
    sq, pitch = 11, 14.3
    x0, y0 = 44, 58
    maxc = max(c for _, c in days) or 1
    def level(c):
        if c == 0:
            return HEAT0
        if c <= 3:
            return HEAT1
        if c <= 7:
            return HEAT2
        if c <= maxc * 0.6:
            return SKY
        return DEEP
    month_labels = {}
    for ci in range(cols):
        sun = start_sunday + dt.timedelta(weeks=ci)
        if sun.month != (sun - dt.timedelta(weeks=1)).month or ci == 0:
            month_labels[ci] = sun.strftime("%b")
        for ri in range(7):
            d = sun + dt.timedelta(days=ri)
            if d > today:
                continue
            c = by_date.get(d.isoformat(), 0)
            x = x0 + ci * pitch
            y = y0 + ri * pitch
            delay = 0.9 + ci * 0.016
            anim = "" if STATIC else f' class="pop" style="animation-delay:{delay:.2f}s"'
            s.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{sq}" height="{sq}" rx="2.5" fill="{level(c)}"{anim}/>')
    for ci, mon in month_labels.items():
        s.append(f'<text x="{x0 + ci * pitch:.0f}" y="{y0 - 8}" font-size="10.5" fill="{FAINT}" style="{MONO}">{mon}</text>')
    for ri, lab in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        s.append(f'<text x="{x0 - 8}" y="{y0 + ri * pitch + 10:.0f}" text-anchor="end" font-size="10.5" fill="{FAINT}" style="{MONO}">{lab}</text>')
    return "".join(s) + svg_close()


def activity(days):
    w, h = 880, 330
    s = [svg_open(w, h)]
    st = stats(days)
    s.append(f'<text x="40" y="38" font-size="12.5" letter-spacing="2.5" fill="{FAINT}" style="{MONO}">ACTIVITY — LAST 12 MONTHS</text>')
    months = st["months"]
    maxv = max(v for _, v in months) or 1
    base_y, top_y = 218, 66
    x, bw, gap = 52, 40, 24.5
    best_key = max(months, key=lambda kv: kv[1])[0]
    for i, (key, v) in enumerate(months):
        bh = max(2, (v / maxv) * (base_y - top_y))
        bx = x + i * (bw + gap)
        color = SKY if key == best_key else BAR_INK
        delay = 1.5 + i * 0.05
        anim = "" if STATIC else f' class="grow" style="animation-delay:{delay:.2f}s"'
        s.append(f'<rect x="{bx:.0f}" y="{base_y - bh:.0f}" width="{bw}" height="{bh:.0f}" rx="4" fill="{color}"{anim}/>')
        lab = dt.datetime.strptime(key, "%Y-%m").strftime("%b")
        vcol = SKY if key == best_key else DIM
        s.append(f'<text x="{bx + bw/2:.0f}" y="{base_y - bh - 8:.0f}" text-anchor="middle" font-size="13" fill="{vcol}" style="{MONO}">{v}</text>')
        s.append(f'<text x="{bx + bw/2:.0f}" y="{base_y + 20}" text-anchor="middle" font-size="11.5" fill="{FAINT}" style="{MONO}">{lab}</text>')
    s.append(f'<line x1="40" y1="{base_y}" x2="840" y2="{base_y}" stroke="{BORDER}"/>')
    # stats strip
    busiest_date = dt.datetime.strptime(st["busiest"][0], "%Y-%m-%d").strftime("%d %b %Y")
    cells = [("TOTAL CONTRIBUTIONS", str(st["total"])),
             ("ACTIVE DAYS", str(st["active"])),
             ("CURRENT STREAK", f'{st["streak"]} days'),
             ("BUSIEST DAY", f'{busiest_date} · {st["busiest"][1]}')]
    cw = 800 / 4
    for i, (lab, val) in enumerate(cells):
        cx = 40 + i * cw
        if i:
            s.append(f'<line x1="{cx:.0f}" y1="262" x2="{cx:.0f}" y2="306" stroke="{BORDER}"/>')
        s.append(f'<text x="{cx + 14:.0f}" y="282" font-size="10.5" letter-spacing="1.5" fill="{FAINT}" style="{MONO}">{lab}</text>')
        s.append(f'<text x="{cx + 14:.0f}" y="306" font-size="19" fill="{INK}" style="{SANS}" font-weight="600">{esc(val)}</text>')
    return "".join(s) + svg_close()


def tile(fname, num_label, count, word, desc_lines, foot, color, delay):
    w, h = 288, 330
    s = [svg_open(w, h, with_font=True)]
    # the whole tile swings up from below, tilted, overshoots and settles (reference entrance)
    if STATIC:
        s.append('<g>')
    else:
        s.append(f'<g class="swing" style="animation-delay:{delay:.2f}s">')
    s.append(f'<rect x="0.5" y="0.5" width="{w-1}" height="5" fill="{color}"/>')
    s.append(f'<rect x="0" y="0" width="{w}" height="{h}" fill="{color}" opacity="0.07"/>')
    s.append(f'<circle cx="252" cy="42" r="15" fill="none" stroke="{color}" stroke-width="1.5" class="ring"/>')
    s.append(f'<circle cx="252" cy="42" r="5" fill="{color}" class="pulse"/>')
    s.append(f'<text x="26" y="48" font-size="11.5" letter-spacing="2.5" fill="{FAINT}" style="{MONO}">{num_label}</text>')
    s.append(count_up(60, 168, count, color, 104, delay, anchor="middle"))
    s.append(f'<text x="26" y="216" font-size="37" fill="{INK}" style="{SERIF};animation-delay:{delay + 0.15:.2f}s" class="rise">{word}</text>')
    for i, line in enumerate(desc_lines):
        s.append(f'<text x="26" y="{248 + i * 20}" font-size="14.5" fill="{DIM}" style="{SANS};animation-delay:{delay + 0.3 + i * 0.08:.2f}s" class="fade">{line}</text>')
    s.append(f'<text x="26" y="312" font-size="12" fill="{color}" style="{MONO};animation-delay:{delay + 0.55:.2f}s" class="fade">{foot}</text>')
    s.append(f'<text x="252" y="313" text-anchor="middle" font-size="16" fill="{color}" class="nudge">→</text>')
    s.append('</g>')
    return "".join(s) + svg_close()


REPOS = [
    ("Aegis", "Scan links, emails &amp; files with 9 live security tools",
     "FastAPI · React 19 · TypeScript · 161 tests", "LIVE · v1.8.0", "SKY"),
    ("Deceptive-Net", "Generate honey tokens with WGAN-GP &amp; ML fraud scoring",
     "Python · PyTorch · FastAPI — 17 tests · CI", "v1.0.0", "PURPLE"),
    ("SIEM", "Auto-block malicious IPs via VirusTotal + OS firewall",
     "Python · Flask · Elastic — 15 tests · CI", "v1.0.0", "RED"),
    ("FoldCrypt", "Encrypt folders with AES, PBKDF2 &amp; SHA-256 manifests",
     "Python · Tkinter — 11 tests · CI", "v1.0.0", "AMBER"),
    ("Z-Security", "Encrypted vault &amp; TOTP authenticator Android app",
     "Kotlin · Compose · SQLCipher — 23 tests · CI", "v1.2.1", "GREEN"),
    ("Wokie", "Offline mesh messaging app with end-to-end encryption",
     "Kotlin · BLE mesh · AES-256-GCM · 96 tests", "v1.2.1", "TEAL"),
]


def repo_card(idx, name, desc, meta, tag, color):
    w, h = 432, 176
    delay = 2.7 + idx * 0.15
    s = [svg_open(w, h)]
    s.append(f'<g class="rise" style="animation-delay:{delay:.2f}s">')
    s.append(f'<circle cx="30" cy="38" r="6" fill="{color}"/>')
    s.append(f'<text x="48" y="46" font-size="23" fill="{INK}" style="{SANS}" font-weight="600">{esc(name)}</text>')
    s.append(f'<text x="{w - 24}" y="46" text-anchor="end" font-size="11.5" fill="{color}" style="{MONO}">{esc(tag)}</text>')
    s.append(f'<text x="26" y="84" font-size="15" fill="{DIM}" style="{SANS}">{desc}</text>')
    s.append(f'<line x1="26" y1="118" x2="{w - 26}" y2="118" stroke="{BORDER}"/>')
    s.append(f'<text x="26" y="146" font-size="12.5" fill="{FAINT}" style="{MONO}">{esc(meta)}</text>')
    s.append('</g>')
    return "".join(s) + svg_close()


def render_all(days):
    cards = {
        "hero.svg": hero(),
        "heatmap.svg": heatmap(days),
        "activity.svg": activity(days),
        "tile-secure.svg": tile("secure", "01 — SECURE", 9, "Secure",
                                ["Live security tools in Aegis —", "phishing, malware, vault &amp;", "audit in one live platform"],
                                "aegis · live demo", SKY, 2.1),
        "tile-build.svg": tile("build", "02 — BUILD", 6, "Build",
                               ["Core projects, documented", "&amp; released — platforms,", "deception research, Android"],
                               "portfolio · live site", RED, 2.3),
        "tile-research.svg": tile("research", "03 — RESEARCH", 1, "Research",
                                  ["Paper presented at ICDSA 2026 —", "a KMAC-based DRBG for robust", "password generation"],
                                  "kmac drbg · under review", AMBER, 2.5),
    }
    for i, (name, desc, meta, tag, color) in enumerate(REPOS):
        cards[f"repo-{i+1}.svg"] = repo_card(i, name, desc, meta, tag, globals()[color])
    return cards


def main():
    if "--fetch" in sys.argv:
        save_days(fetch_calendar())
        print("contributions refreshed")
    days = load_days()
    # Every card is drawn twice: the paper (light) set in cards/ and a dark set
    # in cards/dark/. The README picks between them with <picture> +
    # prefers-color-scheme, so the profile follows the viewer's own theme.
    for theme, sub in (("light", ""), ("dark", "dark")):
        apply_theme(theme)
        out = os.path.join(ROOT, "cards", sub)
        os.makedirs(out, exist_ok=True)
        for fname, content in render_all(days).items():
            with open(os.path.join(out, fname), "w") as f:
                f.write(content)
            print("wrote", os.path.join(sub, fname), len(content), "bytes")


if __name__ == "__main__":
    main()
