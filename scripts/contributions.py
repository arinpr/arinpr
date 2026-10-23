#!/usr/bin/env python3
"""Build the theme-aware, animated contribution panel for the profile README.

Runs in GitHub Actions. Uses GH_STATS_TOKEN (a personal token, so private
contributions are counted) and falls back to GITHUB_TOKEN (public only).
Writes assets/contributions-light.svg and assets/contributions-dark.svg.
"""
import datetime as dt
import json
import os
import sys
import urllib.request

USER = os.environ.get("USERNAME", "arinpr")
TOKEN = os.environ.get("GH_STATS_TOKEN") or os.environ.get("GITHUB_TOKEN")
OUT = os.environ.get("OUT_DIR", "assets")

FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace"

THEMES = {
    "light": dict(fg="#1f2328", muted="#59636e", faint="#818b98", line="#d1d9e0", panel="#f6f8fa",
                  accent="#0969da", ok="#1a7f37",
                  scale=["#eff2f5", "#c6dbf7", "#8cb8f0", "#4493f8", "#0969da"]),
    "dark": dict(fg="#f0f6fc", muted="#9198a1", faint="#656c76", line="#3d444d", panel="#151b23",
                 accent="#4493f8", ok="#3fb950",
                 scale=["#161b22", "#0c2d6b", "#1158c7", "#388bfd", "#79c0ff"]),
}


def gql(query, variables=None):
    if not TOKEN:
        sys.exit("No token: set GH_STATS_TOKEN or GITHUB_TOKEN")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": "profile-contributions"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        sys.exit(f"GraphQL error: {data['errors']}")
    return data["data"]


YEAR_Q = """query($login:String!,$from:DateTime!,$to:DateTime!){
 user(login:$login){contributionsCollection(from:$from,to:$to){
  totalCommitContributions totalPullRequestContributions totalPullRequestReviewContributions
  totalIssueContributions restrictedContributionsCount
  contributionCalendar{totalContributions weeks{contributionDays{date contributionCount weekday}}}}}}"""


def fetch():
    created = gql('query($l:String!){user(login:$l){createdAt}}', {"l": USER})["user"]["createdAt"]
    now = dt.datetime.now(dt.timezone.utc)
    last = gql(YEAR_Q, {"login": USER, "from": (now - dt.timedelta(days=364)).strftime("%Y-%m-%dT00:00:00Z"),
                        "to": now.strftime("%Y-%m-%dT%H:%M:%SZ")})["user"]["contributionsCollection"]
    all_time = 0
    for year in range(int(created[:4]), now.year + 1):
        cc = gql(YEAR_Q, {"login": USER, "from": f"{year}-01-01T00:00:00Z",
                          "to": f"{year}-12-31T23:59:59Z"})["user"]["contributionsCollection"]
        all_time += cc["contributionCalendar"]["totalContributions"]
    return last, all_time, int(created[:4]), now


def streaks(days):
    counts = [d["contributionCount"] for d in days]
    longest = run = 0
    for n in counts:
        run = run + 1 if n else 0
        longest = max(longest, run)
    cur = 0
    i = len(counts) - 1
    if i >= 0 and counts[i] == 0:  # today not counted yet doesn't break the streak
        i -= 1
    while i >= 0 and counts[i]:
        cur += 1
        i -= 1
    return cur, longest


def levels(days):
    nz = sorted(d["contributionCount"] for d in days if d["contributionCount"])
    if not nz:
        return lambda n: 0
    q = [nz[int(len(nz) * p)] for p in (0.25, 0.5, 0.75)]
    return lambda n: 0 if n == 0 else 1 if n <= q[0] else 2 if n <= q[1] else 3 if n <= q[2] else 4


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


def fmt(n):
    return f"{n:,}"


def render(mode, last, all_time, since, now):
    c = THEMES[mode]
    cal = last["contributionCalendar"]
    weeks = [w for w in cal["weeks"] if w["contributionDays"]]
    days = [d for w in weeks for d in w["contributionDays"]]
    lv = levels(days)
    cur, longest = streaks(days)
    best = max(days, key=lambda d: d["contributionCount"]) if days else None

    W, cell, gap = 1200, 14, 3
    gx0, gy0 = 92, 196
    H = gy0 + 7 * (cell + gap) + 46

    tiles = [
        (fmt(cal["totalContributions"]), "contributions", "last 12 months"),
        (fmt(all_time), "all-time", f"since {since}"),
        (fmt(last["totalCommitContributions"]), "commits", "last 12 months"),
        (fmt(last["totalPullRequestContributions"] + last["totalPullRequestReviewContributions"]), "PRs + reviews", "last 12 months"),
        (f"{cur} d", "current streak", f"longest {longest} d"),
    ]

    private = bool(os.environ.get("GH_STATS_TOKEN")) or last["restrictedContributionsCount"] > 0
    scope = "PUBLIC + PRIVATE" if private else "PUBLIC"
    aria_scope = "including private work" if private else "public repositories"
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
           f'aria-label="{cal["totalContributions"]} contributions in the last 12 months, {aria_scope}">',
           """<style>
.f{opacity:0;animation:fi .7s cubic-bezier(.2,.7,.2,1) forwards}
@keyframes fi{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.cl{opacity:0;animation:cl .5s ease-out forwards}
@keyframes cl{from{opacity:0;transform:scale(.4)}to{opacity:1;transform:none}}
.cl{transform-box:fill-box;transform-origin:center}
.sweep{animation:sweep 7s ease-in-out 2s infinite}
@keyframes sweep{0%{transform:translateX(0);opacity:0}8%{opacity:.9}92%{opacity:.9}100%{transform:translateX(%SW%px);opacity:0}}
.pulse{animation:pulse 2s ease-in-out infinite}@keyframes pulse{50%{opacity:.3}}
@media (prefers-reduced-motion: reduce){.f,.cl,.sweep,.pulse{animation:none!important;opacity:1!important;transform:none!important}.sweep{display:none}}
</style>""".replace("%SW%", str(len(weeks) * (cell + gap))),
           f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="14" fill="none" stroke="{c["line"]}"/>',
           f'<text x="36" y="44" font-family="{MONO}" font-size="12" font-weight="600" letter-spacing="1.5" fill="{c["faint"]}">CONTRIBUTIONS  ·  {scope}</text>',
           f'<g class="f"><circle cx="{W-300}" cy="40" r="4" fill="{c["ok"]}" class="pulse"/>'
           f'<text x="{W-288}" y="44" font-family="{MONO}" font-size="12" fill="{c["muted"]}">Updated {now:%d %b %Y, %H:%M} UTC</text></g>']

    tw = (W - 72) / len(tiles)
    for i, (big, lbl, sub) in enumerate(tiles):
        x = 36 + i * tw
        d = 0.1 + 0.08 * i
        if i:
            out.append(f'<line x1="{x-18:.1f}" y1="72" x2="{x-18:.1f}" y2="150" stroke="{c["line"]}"/>')
        out.append(f'<g class="f" style="animation-delay:{d:.2f}s">'
                   f'<text x="{x:.1f}" y="106" font-family="{FONT}" font-size="32" font-weight="700" letter-spacing="-0.5" fill="{c["fg"]}">{esc(big)}</text>'
                   f'<text x="{x:.1f}" y="132" font-family="{FONT}" font-size="14" font-weight="600" fill="{c["muted"]}">{esc(lbl)}</text>'
                   f'<text x="{x:.1f}" y="150" font-family="{FONT}" font-size="12.5" fill="{c["faint"]}">{esc(sub)}</text></g>')

    for i, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="{gx0-12}" y="{gy0 + i*(cell+gap) + 11}" text-anchor="end" font-family="{MONO}" '
                   f'font-size="11" fill="{c["faint"]}">{name}</text>')
    last_month, last_label_wi = None, -9
    for wi, w in enumerate(weeks):
        first = w["contributionDays"][0]["date"]
        m = first[5:7]
        if m != last_month:
            if 0 < wi < len(weeks) - 2 and wi - last_label_wi >= 3:
                label = dt.date.fromisoformat(first).strftime("%b")
                out.append(f'<text x="{gx0 + wi*(cell+gap)}" y="{gy0-12}" font-family="{MONO}" font-size="11" fill="{c["faint"]}">{label}</text>')
                last_label_wi = wi
            last_month = m
        for d in w["contributionDays"]:
            x = gx0 + wi * (cell + gap)
            y = gy0 + d["weekday"] * (cell + gap)
            n = d["contributionCount"]
            delay = 0.25 + wi * 0.018 + d["weekday"] * 0.01
            out.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3.5" fill="{c["scale"][lv(n)]}" '
                       f'class="cl" style="animation-delay:{delay:.3f}s"><title>{n} on {d["date"]}</title></rect>')
    gh = 7 * (cell + gap) - gap
    out.append(f'<rect x="{gx0-2}" y="{gy0-3}" width="3" height="{gh+6}" rx="1.5" fill="{c["accent"]}" opacity="0" class="sweep"/>')

    gw = len(weeks) * (cell + gap)
    lx = gx0 + gw + 28
    out.append(f'<text x="{lx}" y="{gy0+12}" font-family="{MONO}" font-size="11" fill="{c["faint"]}">Less</text>')
    for i, col in enumerate(c["scale"]):
        out.append(f'<rect x="{lx + i*19}" y="{gy0+22}" width="15" height="15" rx="3.5" fill="{col}"/>')
    out.append(f'<text x="{lx + 5*19 - 4}" y="{gy0+56}" text-anchor="end" font-family="{MONO}" font-size="11" fill="{c["faint"]}">More</text>')
    if best and best["contributionCount"]:
        bd = dt.date.fromisoformat(best["date"]).strftime("%d %b %Y")
        out.append(f'<text x="{lx}" y="{gy0+100}" font-family="{FONT}" font-size="12.5" fill="{c["faint"]}">Best day</text>')
        out.append(f'<text x="{lx}" y="{gy0+120}" font-family="{FONT}" font-size="14" font-weight="600" fill="{c["muted"]}">{best["contributionCount"]} on {bd}</text>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    last, all_time, since, now = fetch()
    os.makedirs(OUT, exist_ok=True)
    for mode in THEMES:
        with open(os.path.join(OUT, f"contributions-{mode}.svg"), "w") as f:
            f.write(render(mode, last, all_time, since, now))
    print("contributions:", last["contributionCalendar"]["totalContributions"],
          "private:", last["restrictedContributionsCount"], "all-time:", all_time)


if __name__ == "__main__":
    main()
