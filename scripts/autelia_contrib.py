"""Render the GitHub contribution calendar as an animated Autelia-style SVG.

A ship sweeps across the year and shoots down each week's contributions,
which respawn as the next wave. Uses only the standard library.

Usage:
    GITHUB_TOKEN=... python scripts/autelia_contrib.py --user OmarDavidd --out dist
    python scripts/autelia_contrib.py --input calendar.json --out dist
"""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date contributionLevel } }
      }
    }
  }
}
"""

LEVELS = ["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"]

THEMES = {
    "dark": {
        "bg": "#0d1117",
        "empty": "#161b22",
        "levels": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
        "ship": "#00e676",
        "shot": "#b9f6ca",
        "flash": "#ffffff",
        "text": "#8b949e",
        "accent": "#00e676",
    },
    "light": {
        "bg": "#ffffff",
        "empty": "#ebedf0",
        "levels": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "ship": "#00a844",
        "shot": "#00c853",
        "flash": "#0d1117",
        "text": "#57606a",
        "accent": "#00a844",
    },
}

CELL = 11
GAP = 3
STEP = CELL + GAP
MARGIN_X = 20
GRID_Y = 44
DURATION = 16.0  # seconds per full sweep
SWEEP = 0.94  # fraction of the cycle the ship spends moving forward
TRAVEL = 0.012  # fraction of the cycle a shot takes to cross the grid


def fetch_calendar(user: str, token: str) -> dict:
    body = json.dumps({"query": QUERY, "variables": {"login": user}}).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except OSError as error:
        sys.exit(f"Failed to fetch contributions: {error}")
    if "errors" in payload or not payload.get("data", {}).get("user"):
        sys.exit(f"GitHub API returned an error: {payload.get('errors', payload)}")
    return payload


def extract_calendar(payload: dict) -> tuple[int, list[list[dict]]]:
    calendar = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = [week["contributionDays"] for week in calendar["weeks"]]
    return calendar["totalContributions"], weeks


def column_hit_time(column: int, columns: int) -> float:
    """Seconds into the cycle when the ship fires on a column."""
    return DURATION * SWEEP * column / max(columns - 1, 1)


def render(total: int, weeks: list[list[dict]], theme: dict) -> str:
    columns = len(weeks)
    width = MARGIN_X * 2 + columns * STEP - GAP
    ship_y = GRID_Y + 7 * STEP + 14
    height = ship_y + 30
    first_x = MARGIN_X + CELL / 2
    last_x = MARGIN_X + (columns - 1) * STEP + CELL / 2
    sweep_pct = SWEEP * 100

    cells, shots = [], []
    for col, days in enumerate(weeks):
        x = MARGIN_X + col * STEP
        hit = column_hit_time(col, columns)
        has_target = False
        for day in days:
            row = int(day.get("weekday", _weekday(day["date"])))
            y = GRID_Y + row * STEP
            level = LEVELS.index(day["contributionLevel"])
            cells.append(
                f'<rect class="empty" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2"/>'
            )
            if level == 0:
                continue
            has_target = True
            # Lower rows are hit first as the shot travels upward.
            delay = hit + DURATION * TRAVEL * (6 - row) / 6
            cells.append(
                f'<rect class="enemy" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" '
                f'fill="{theme["levels"][level]}" style="animation-delay:{delay:.3f}s"/>'
            )
        if has_target:
            shots.append(
                f'<rect class="shot" x="{x + CELL / 2 - 1}" y="{ship_y - 10}" width="2" height="8" '
                f'style="animation-delay:{hit:.3f}s"/>'
            )

    climb = ship_y - GRID_Y
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{total} contributions in the last year">
<style>
  .empty {{ fill: {theme["empty"]}; }}
  .enemy {{ transform-box: fill-box; transform-origin: center; animation: burst {DURATION}s linear infinite both; }}
  .shot {{ fill: {theme["shot"]}; opacity: 0; animation: fire {DURATION}s linear infinite; }}
  .ship {{ animation: fly {DURATION}s linear infinite; }}
  .label {{ font: 600 12px 'Segoe UI', Ubuntu, sans-serif; fill: {theme["text"]}; }}
  .count {{ fill: {theme["accent"]}; }}
  @keyframes burst {{
    0% {{ opacity: 1; transform: scale(1); }}
    1% {{ opacity: 1; transform: scale(1.4); fill: {theme["flash"]}; }}
    3% {{ opacity: 0; transform: scale(0); }}
    84% {{ opacity: 0; transform: scale(0); }}
    90% {{ opacity: 1; transform: scale(1); }}
    100% {{ opacity: 1; transform: scale(1); }}
  }}
  @keyframes fire {{
    0% {{ opacity: 1; transform: translateY(0); }}
    {TRAVEL * 100:.2f}% {{ opacity: 1; transform: translateY(-{climb}px); }}
    {TRAVEL * 100 + 0.01:.2f}% {{ opacity: 0; transform: translateY(-{climb}px); }}
    100% {{ opacity: 0; }}
  }}
  @keyframes fly {{
    0% {{ transform: translateX({first_x}px); }}
    {sweep_pct:.0f}% {{ transform: translateX({last_x}px); }}
    100% {{ transform: translateX({first_x}px); }}
  }}
  @media (prefers-reduced-motion: reduce) {{
    .enemy, .shot, .ship {{ animation: none; }}
  }}
</style>
<rect width="100%" height="100%" rx="8" fill="{theme["bg"]}"/>
<text class="label" x="{MARGIN_X}" y="26"><tspan class="count">{total}</tspan> contribuciones en el último año</text>
{"".join(cells)}
{"".join(shots)}
<g class="ship"><polygon points="0,{ship_y - 9} 7,{ship_y + 5} 0,{ship_y + 1} -7,{ship_y + 5}" fill="{theme["ship"]}"/></g>
</svg>
"""


def _weekday(date: str) -> int:
    """Sunday-first weekday, matching GitHub's calendar rows."""
    from datetime import date as _date

    return (_date.fromisoformat(date).weekday() + 1) % 7


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--user", default=os.environ.get("GITHUB_USER"))
    parser.add_argument("--input", type=Path, help="Read a saved GraphQL response instead of calling the API")
    parser.add_argument("--out", type=Path, default=Path("dist"))
    args = parser.parse_args()

    if args.input:
        payload = json.loads(args.input.read_text())
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not args.user or not token:
            sys.exit("Provide --user and the GITHUB_TOKEN environment variable, or use --input.")
        payload = fetch_calendar(args.user, token)

    total, weeks = extract_calendar(payload)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, theme in THEMES.items():
        (args.out / f"autelia-{name}.svg").write_text(render(total, weeks, theme))
    print(f"Rendered {total} contributions across {len(weeks)} weeks into {args.out}/")


if __name__ == "__main__":
    main()
