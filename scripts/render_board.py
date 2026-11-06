"""renders the profile's svgs into assets/ from live github data.

stdlib only. text is drawn from assets/flap-glyphs.json, so the svgs need no
fonts and look the same everywhere. if the api call fails, the existing svgs
stay as they are.
"""
import json
import os
import random
import urllib.request
from datetime import date, datetime, timezone

USER = "adamentwistle"
ASSETS = "assets"

# flight code, name on the board, repo
FLIGHTS = [
    ("FS", "FABLE SKILLS", "fable-skills"),
    ("LW", "LEGWORK", "legwork"),
    ("OR", "ORCHI", "orchi-build"),
    ("HD", "HERDR DEPARTURES", "herdr-departures"),
    ("CW", "CLAUDE WRAPPED", "claude-code-wrapped"),
    ("EK", "AGENT ENG KIT", "agent-eng-kit"),
]
JOKE_ROW = ("AG 000", "AGI", "DELAYED")
TICKER = "PLEASE DO NOT LEAVE AGENTS UNATTENDED. UNATTENDED AGENTS WILL BE MERGED TO MAIN."

# fable-skills readme, benchmark 3: mean score, bare then with skills
BENCHMARK = [("HAIKU 4.5", 44, 53), ("SONNET 5", 74, 80), ("OPUS 5", 90, 95)]
BENCHMARK_REFERENCE = ("FABLE 5.1 BARE", 94)

# small flap labels used as headings and links in the readme
LABELS = {
    "h-now-boarding": "NOW BOARDING",
    "h-flight-log": "FLIGHT LOG",
    "h-arrivals": "ARRIVALS",
    "h-ground-crew": "GROUND CREW",
    "n-orchi": "ORCHI",
    "n-mods": "CLAUDE CODE MODS",
    "n-territory": "HERDR TERRITORY",
    "n-wrapped": "CLAUDE CODE WRAPPED",
    "l-site": "ADAMENTWISTLE.COM",
    "l-x": "@AAE_ON_X",
    "l-linkedin": "LINKEDIN",
}

AMBER = "#ffc72c"
AMBER_DIM = "#7d6115"
LABEL = "#b08a2c"
SEAM = "#050505"
FLIP_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
STEP = 0.075  # seconds per flap
LOOP = 14  # seconds between remark refreshes

QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(privacy: PUBLIC, ownerAffiliations: OWNER, first: 100) {
      totalCount
      nodes { name stargazerCount pushedAt }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date } }
      }
    }
  }
}
"""


def fetch():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("no GH_TOKEN or GITHUB_TOKEN set")
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-board"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    if data.get("errors") or not data.get("data", {}).get("user"):
        raise RuntimeError(f"graphql error: {data.get('errors')}")
    return data["data"]["user"]


def remark(pushed_at, today):
    days = (today - datetime.fromisoformat(pushed_at.replace("Z", "+00:00")).date()).days
    if days <= 3:
        return "BOARDING"
    if days <= 30:
        return "ON TIME"
    return "DEPARTED"


def streak(days, today):
    """days: [(date, count)] oldest first. today not counting yet doesn't break it."""
    run = 0
    for d, count in reversed(days):
        if d >= today and count == 0:
            continue
        if count == 0:
            break
        run += 1
    return run


class Canvas:
    def __init__(self, glyphs):
        self.glyphs = glyphs
        self.used = set()
        self.out = []

    def add(self, s):
        self.out.append(s)

    def glyph(self, ch, x, base, scale):
        if ch == " ":
            return ""
        self.used.add(ch)
        ref = "g" + format(ord(ch), "x")
        return f'<use href="#{ref}" transform="translate({x:.1f} {base:.1f}) scale({scale:.4f})"/>'

    def text(self, text, x, y, size, fill=LABEL, spacing=1.12):
        """plain text, no cells, as a string. y is the baseline, size the cap height."""
        scale = size / 730
        advance = 600 * scale * spacing
        parts = [self.glyph(c, x + i * advance, y, scale) for i, c in enumerate(text)]
        return f'<g fill="{fill}">{"".join(parts)}</g>'

    def label(self, text, x, y, size, fill=LABEL, spacing=1.12):
        self.add(self.text(text, x, y, size, fill, spacing))

    def cell(self, ch, x, y, w, h, rng, delay, lit=False, loop=False):
        """one split-flap cell. the resting state is the real character, so a
        renderer with no animation still shows the right text."""
        scale = (h * 0.56) / 730
        gx = (w - 600 * scale) / 2
        base = (h + h * 0.56) / 2
        half = h / 2
        top, bottom = (AMBER, "#eeb71e") if lit else ("url(#ct)", "url(#cb)")
        ink = "#0b0b0b" if lit else AMBER
        glow = "" if lit else ' filter="url(#glow)"'
        cls = ' class="lit"' if lit else ""
        s = [f'<g transform="translate({x} {y})"{cls}>']
        s.append(f'<rect width="{w}" height="{half:.1f}" rx="3" fill="{top}"/>')
        s.append(f'<rect y="{half:.1f}" width="{w}" height="{half:.1f}" rx="3" fill="{bottom}"/>')
        if ch != " ":
            flips = rng.randint(3, 8)
            strip = [self.glyph(ch, gx, base, scale)]
            for k in range(1, flips + 1):
                strip.append(self.glyph(rng.choice(FLIP_CHARS), gx, base + k * h, scale))
            if loop:
                timing = f"animation-name:l{flips};animation-duration:{LOOP}s;animation-iteration-count:infinite;"
            else:
                timing = (
                    f"animation-duration:{flips * STEP:.2f}s;"
                    f"animation-timing-function:steps({flips},end);"
                )
            s.append(f'<svg width="{w}" height="{h}"><g fill="{ink}"{glow}>')
            s.append(
                f'<g class="f" style="--h:-{flips * h}px;{timing}'
                f'animation-delay:{delay:.2f}s">{"".join(strip)}</g>'
            )
            s.append("</g></svg>")
        s.append(f'<rect y="{half - 0.75:.2f}" width="{w}" height="1.5" fill="{SEAM}"/>')
        # the little hinge pins either side of the seam
        pin = "#0b0b0b" if lit else "#3d3d3d"
        s.append(f'<rect x="1" y="{half - 2.5:.1f}" width="2" height="5" fill="{pin}"/>')
        s.append(f'<rect x="{w - 3}" y="{half - 2.5:.1f}" width="2" height="5" fill="{pin}"/>')
        s.append("</g>")
        self.add("".join(s))

    def cells(self, text, x, y, w, h, pitch, seed, delay=0.0, **kw):
        rng = random.Random(seed)
        for i, ch in enumerate(text):
            self.cell(ch, x + i * pitch, y, w, h, rng, delay + i * 0.03 + rng.random() * 0.1, **kw)

    def svg(self, width, height, title, extra_css="", panel=True):
        defs = "".join(
            f'<path id="g{format(ord(c), "x")}" d="{self.glyphs[c]}"/>' for c in sorted(self.used)
        )
        defs += (
            '<linearGradient id="ct" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#2c2c2c"/><stop offset="1" stop-color="#1e1e1e"/></linearGradient>'
            '<linearGradient id="cb" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#1a1a1a"/><stop offset="1" stop-color="#121212"/></linearGradient>'
            '<linearGradient id="pn" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#121212"/><stop offset="1" stop-color="#070707"/></linearGradient>'
            '<filter id="glow" x="-40%" y="-40%" width="180%" height="180%">'
            '<feGaussianBlur stdDeviation="2.4" result="b"/>'
            '<feComponentTransfer in="b" result="s"><feFuncA type="linear" slope=".55"/></feComponentTransfer>'
            '<feMerge><feMergeNode in="s"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        )
        loops = "".join(
            f"@keyframes l{n}{{0%{{transform:translateY(var(--h));animation-timing-function:steps({n},end)}}"
            f"{n * STEP / LOOP * 100:.2f}%,100%{{transform:translateY(0)}}}}"
            for n in range(3, 9)
        )
        css = (
            "@keyframes flap{from{transform:translateY(var(--h))}to{transform:translateY(0)}}"
            ".f{animation-name:flap;animation-fill-mode:backwards}"
            f"{loops}{extra_css}"
            "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
        )
        back = (
            f'<rect x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="14" '
            'fill="url(#pn)" stroke="#2b2b2b"/>'
            if panel
            else ""
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}" role="img" aria-label="{title}">'
            f"<title>{title}</title><style>{css}</style><defs>{defs}</defs>"
            f'{back}{"".join(self.out)}</svg>'
        )


def render_board(user, glyphs, today):
    c = Canvas(glyphs)
    left, pitch = 58, 36
    repos = {r["name"]: r for r in user["repositories"]["nodes"]}

    c.cells("ADAM ENTWISTLE", left, 40, 60, 84, 65, "title")

    # date block, top right
    right = 1280 - left - 6 * pitch + 4
    c.label("LAST REFRESH", right, 52, 11)
    c.cells(today.strftime("%d %b").upper(), right, 66, 32, 44, pitch, "date", delay=0.5)
    plane = (
        "M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22"
        "l3.5-1 3.5 1v-1.5L13 19v-5.5z"
    )
    c.add(
        f'<path d="{plane}" fill="{AMBER}" '
        f'transform="translate({right + 196} 34) rotate(45 12 12) scale(.9)"/>'
    )

    c.cells("APPLIED AI ENGINEER", left, 142, 32, 44, pitch, "role", delay=0.5)
    c.cells("QUICKNODE", left + 20 * pitch, 142, 32, 44, pitch, "co", delay=0.9)
    c.label("AGENTIC SYSTEMS YOU CAN MEASURE AND TRUST", left, 222, 15, fill=AMBER, spacing=1.2)

    cols = (left, left + 7 * pitch, 1280 - left - 8 * pitch + 4)
    for x, name in zip(cols, ("FLIGHT", "DESTINATION", "REMARKS")):
        c.label(name, x, 262, 11)

    def lamp(y, note):
        if note == "DEPARTED":
            c.add(f'<circle cx="36" cy="{y + 22}" r="5" fill="#2e2e2e"/>')
        else:
            cls = {"BOARDING": ' class="lamp"', "DELAYED": ' class="lamp fast"'}.get(note, "")
            c.add(f'<circle cx="36" cy="{y + 22}" r="5" fill="{AMBER}" filter="url(#glow)"{cls}/>')

    y = 274
    for i, (code, name, repo) in enumerate(FLIGHTS):
        r = repos.get(repo, {"stargazerCount": 0, "pushedAt": None})
        note = remark(r["pushedAt"], today) if r["pushedAt"] else "DEPARTED"
        delay = 0.9 + i * 0.14
        lamp(y, note)
        c.cells(f"{code} {r['stargazerCount']:03d}", cols[0], y, 32, 44, pitch, f"f{i}", delay)
        c.cells(name.ljust(16), cols[1], y, 32, 44, pitch, f"d{i}", delay + 0.1)
        c.cells(note.ljust(8), cols[2], y, 32, 44, pitch, f"r{i}", delay + 0.2, loop=True)
        y += 50

    delay = 0.9 + len(FLIGHTS) * 0.14
    flight, name, note = JOKE_ROW
    lamp(y, note)
    c.cells(flight, cols[0], y, 32, 44, pitch, "jf", delay)
    c.cells(name.ljust(16), cols[1], y, 32, 44, pitch, "jd", delay + 0.1)
    c.cells(note.ljust(8), cols[2], y, 32, 44, pitch, "jr", delay + 0.2, lit=True, loop=True)
    y += 44 + 20

    # announcement ticker, two copies so the scroll joins up
    width = 1280 - 2 * left
    size, spacing = 13, 1.2
    advance = 600 * size / 730 * spacing
    message = TICKER + " " * 14
    run = len(message) * advance
    c.add(f'<rect x="{left}" y="{y}" width="{width}" height="36" rx="4" fill="#040404" stroke="#262626"/>')
    c.add(
        f'<svg x="{left}" y="{y}" width="{width}" height="36"><g class="tick" style="--w:-{run:.1f}px">'
        f"{c.text(message, 14, 23, size, fill=AMBER, spacing=spacing)}"
        f"{c.text(message, 14 + run, 23, size, fill=AMBER, spacing=spacing)}</g></svg>"
    )
    y += 36

    css = (
        "@keyframes pulse{50%{opacity:.62}}.lit{animation:pulse 2.4s ease-in-out 4s infinite}"
        "@keyframes lamp{50%{opacity:.25}}.lamp{animation:lamp 2s ease-in-out infinite}"
        ".fast{animation-duration:.9s}"
        "@keyframes tick{to{transform:translateX(var(--w))}}.tick{animation:tick 38s linear infinite}"
    )
    return c.svg(
        1280,
        y + 30,
        "adam entwistle, applied ai engineer at quicknode. a split-flap departures board of his projects.",
        css,
    )


def render_telemetry(user, glyphs, today):
    c = Canvas(glyphs)
    left = 58
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    days = [
        (date.fromisoformat(d["date"]), d["contributionCount"])
        for w in weeks
        for d in w["contributionDays"]
    ]
    stars = sum(r["stargazerCount"] for r in user["repositories"]["nodes"])
    stats = [
        ("STARS", str(stars)),
        ("CONTRIBUTIONS / 12 MONTHS", str(cal["totalContributions"])),
        ("PUBLIC REPOS", str(user["repositories"]["totalCount"])),
        ("DAY STREAK", str(streak(days, today))),
    ]
    x_positions = (left, left + 250, left + 640, left + 950)
    for (label, value), x in zip(stats, x_positions):
        c.label(label, x, 50, 11)
        c.cells(value, x, 62, 44, 62, 48, f"s{label}")

    # contribution heatmap, one column per week
    counts = sorted(n for _, n in days if n > 0)

    def level(n):
        if n == 0 or not counts:
            return 0
        rank = sum(1 for v in counts if v <= n) / len(counts)
        return 1 + min(3, int(rank * 4 - 1e-9))

    shades = ("#1a1a1a", "#5c4610", "#96721a", "#cf9f24", AMBER)
    pitch, size, top = 22, 19, 176
    month_seen = None
    for wi, week in enumerate(weeks):
        x = left + wi * pitch
        first = date.fromisoformat(week["contributionDays"][0]["date"])
        if first.month != month_seen and wi < len(weeks) - 2:
            if month_seen is not None:
                c.label(first.strftime("%b").upper(), x, top - 12, 10)
            month_seen = first.month
        rects = []
        for d in week["contributionDays"]:
            row = date.fromisoformat(d["date"]).isoweekday() % 7
            fill = shades[level(d["contributionCount"])]
            rects.append(
                f'<rect x="{x}" y="{top + row * pitch}" width="{size}" height="{size}" '
                f'rx="3" fill="{fill}"/>'
            )
        c.add(f'<g class="w" style="animation-delay:{0.6 + wi * 0.018:.2f}s">{"".join(rects)}</g>')

    css = "@keyframes rise{from{opacity:0}to{opacity:1}}.w{animation:rise .35s ease-out backwards}"
    return c.svg(
        1280,
        top + 7 * pitch + 28,
        "github activity: stars, contributions and a heatmap of the last year.",
        css,
    )


def render_benchmark(glyphs):
    c = Canvas(glyphs)
    left = 58
    c.cells("FABLE SKILLS", left, 38, 32, 44, 36, "bench")
    c.label("39 SKILLS. SAME TASKS WITH AND WITHOUT THEM, GRADED BLIND.", left, 112, 13, fill=AMBER, spacing=1.15)

    # legend
    c.add(f'<rect x="946" y="44" width="16" height="16" rx="2" fill="{AMBER_DIM}"/>')
    c.label("BARE", 970, 58, 11)
    c.add(f'<rect x="1040" y="44" width="16" height="16" rx="2" fill="{AMBER}"/>')
    c.label("WITH SKILLS", 1064, 58, 11)

    track_x, track_w, bar_h = 196, 880, 28
    y = 166
    ref_name, ref_value = BENCHMARK_REFERENCE
    ref_x = track_x + track_w * ref_value / 100
    for i, (model, bare, skilled) in enumerate(BENCHMARK):
        c.label(model, left, y + 20, 13, fill=AMBER)
        c.add(f'<rect x="{track_x}" y="{y}" width="{track_w}" height="{bar_h}" rx="3" fill="#191919"/>')
        lift_x = track_x + track_w * bare / 100
        c.add(
            f'<rect class="bar" style="animation-delay:{0.5 + i * 0.25:.2f}s" x="{track_x}" y="{y}" '
            f'width="{track_w * skilled / 100:.1f}" height="{bar_h}" rx="3" fill="{AMBER}"/>'
        )
        c.add(
            f'<rect class="bar" style="animation-delay:{0.3 + i * 0.25:.2f}s" x="{track_x}" y="{y}" '
            f'width="{lift_x - track_x:.1f}" height="{bar_h}" rx="3" fill="{AMBER_DIM}"/>'
        )
        c.label(f"{bare} > {skilled}", track_x + track_w + 22, y + 20, 13, fill=AMBER)
        y += 48

    c.add(
        f'<line x1="{ref_x:.1f}" y1="150" x2="{ref_x:.1f}" y2="{y - 8}" stroke="#f4f4f4" '
        'stroke-width="2" stroke-dasharray="5 4"/>'
    )
    text = f"{ref_name} {ref_value}"
    c.label(text, ref_x - len(text) * 8.3 + 2, 142, 11, fill="#f4f4f4")
    c.label("MEAN SCORE % ACROSS 9 TASK AREAS, 5 RUNS PER CELL", left, y + 18, 11)

    css = (
        "@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}"
        ".bar{transform-box:fill-box;transform-origin:0 0;animation:grow .9s cubic-bezier(.2,.7,.2,1) backwards}"
    )
    return c.svg(
        1280,
        y + 44,
        "fable-skills benchmark: mean score bare then with skills. haiku 4.5 44 to 53, sonnet 5 74 to 80, "
        "opus 5 90 to 95. fable 5.1 bare scores 94.",
        css,
    )


def render_label(glyphs, name, text):
    c = Canvas(glyphs)
    w, h, pitch = 30, 42, 33
    c.cells(text, 1, 1, w, h, pitch, name)
    return c.svg(len(text) * pitch + 1, h + 2, text.lower(), panel=False)


def main():
    with open(os.path.join(ASSETS, "flap-glyphs.json"), encoding="utf-8") as f:
        glyphs = json.load(f)["glyphs"]
    try:
        user = fetch()
    except Exception as e:  # keep yesterday's board rather than fail the refresh
        print(f"board not refreshed: {e}")
        return
    today = datetime.now(timezone.utc).date()
    rendered = {
        "board.svg": render_board(user, glyphs, today),
        "telemetry.svg": render_telemetry(user, glyphs, today),
        "benchmark.svg": render_benchmark(glyphs),
    }
    for name, text in LABELS.items():
        rendered[f"{name}.svg"] = render_label(glyphs, name, text)
    for name, svg in rendered.items():
        with open(os.path.join(ASSETS, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(svg)
    print(f"rendered {len(rendered)} svgs, board {len(rendered['board.svg']) // 1024} KB")


if __name__ == "__main__":
    main()
