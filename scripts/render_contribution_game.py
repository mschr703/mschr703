"""Render a GitHub-style contribution grid with a small ship collecting active days."""

from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 880, 205
LEFT, TOP = 68, 62
CELL, STEP = 10, 14
BACKGROUND = "#0d1117"
EMPTY = "#161b22"
BORDER = "#30363d"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
GREENS = (EMPTY, "#0e4429", "#006d32", "#26a641", "#39d353")
LEVELS = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def load_font(size: int) -> ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


FONT = load_font(12)
SMALL = load_font(10)


def fetch_calendar(username: str) -> dict:
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GH_TOKEN is required to fetch the contribution calendar")
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            weeks {
              contributionDays {
                date
                contributionCount
                contributionLevel
              }
            }
          }
        }
      }
    }
    """
    payload = json.dumps({"query": query, "variables": {"login": username}}).encode("utf-8")
    request = Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "mschr703-contribution-game",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"GitHub GraphQL returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError("Could not reach GitHub GraphQL") from exc

    if result.get("errors"):
        raise RuntimeError("GitHub GraphQL rejected the contribution query")
    user = result.get("data", {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub user {username!r} was not found")
    return user["contributionsCollection"]["contributionCalendar"]


def prepare_grid(calendar: dict) -> tuple[list, dict]:
    weeks = calendar["weeks"][-53:]
    if not weeks or len(weeks) > 53:
        raise ValueError("Expected up to 53 weeks of contribution data")
    active = {}
    for col, week in enumerate(weeks):
        for day in week["contributionDays"]:
            row = (date.fromisoformat(day["date"]).weekday() + 1) % 7
            level = LEVELS[day["contributionLevel"]]
            if day["contributionCount"] > 0 and level > 0:
                active[(col, row)] = level
    return weeks, active


def make_backdrop(weeks: list) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, WIDTH - 1, HEIGHT - 1), radius=8, outline=BORDER, width=1)
    draw.text((24, 17), "Contributions in the last year", fill=TEXT, font=FONT)

    last_month = None
    for col, week in enumerate(weeks):
        if not week["contributionDays"]:
            continue
        month = date.fromisoformat(week["contributionDays"][0]["date"]).month
        if month != last_month:
            draw.text((LEFT + col * STEP, 43), MONTHS[month - 1], fill=MUTED, font=SMALL)
            last_month = month

    for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        draw.text((24, TOP + row * STEP - 1), label, fill=MUTED, font=SMALL)

    for col, week in enumerate(weeks):
        for day in week["contributionDays"]:
            row = (date.fromisoformat(day["date"]).weekday() + 1) % 7
            x, y = LEFT + col * STEP, TOP + row * STEP
            draw.rounded_rectangle((x, y, x + CELL - 1, y + CELL - 1), radius=2, fill=EMPTY)

    legend_y = 176
    draw.text((WIDTH - 153, legend_y), "Less", fill=MUTED, font=SMALL)
    for level, color in enumerate(GREENS):
        x = WIDTH - 119 + level * 14
        draw.rounded_rectangle((x, legend_y, x + 9, legend_y + 9), radius=2, fill=color)
    draw.text((WIDTH - 42, legend_y), "More", fill=MUTED, font=SMALL)
    return image


def draw_ship(draw: ImageDraw.ImageDraw, x: int, y: int, direction: int, spark: bool) -> None:
    def point(dx: int, dy: int) -> tuple[int, int]:
        return (x + direction * dx, y + dy)

    draw.polygon([point(-7, 0), point(-12, -3), point(-12, 3)], fill="#d29922")
    draw.polygon([point(8, 0), point(-4, -6), point(-1, 0), point(-4, 6)], fill="#58a6ff")
    draw.polygon([point(4, 0), point(-3, -3), point(-2, 0), point(-3, 3)], fill="#c9d1d9")
    draw.ellipse((x - 2, y - 2, x + 1, y + 1), fill="#0d1117")
    if spark:
        draw.point((x, y - 9), fill="#e3b341")
        draw.point((x - direction * 4, y + 9), fill="#e3b341")


def render_frame(
    backdrop: Image.Image,
    active: dict,
    eaten: set,
    ship: tuple[int, int, int] | None = None,
    spark: bool = False,
) -> Image.Image:
    image = backdrop.copy()
    draw = ImageDraw.Draw(image)
    for (col, row), level in active.items():
        if (col, row) in eaten:
            continue
        x, y = LEFT + col * STEP, TOP + row * STEP
        draw.rounded_rectangle((x, y, x + CELL - 1, y + CELL - 1), radius=2, fill=GREENS[level])
    if ship:
        col, row, direction = ship
        draw_ship(draw, LEFT + col * STEP + CELL // 2, TOP + row * STEP + CELL // 2, direction, spark)
    return image


def animate(weeks: list, active: dict, output: Path) -> None:
    backdrop = make_backdrop(weeks)
    eaten: set[tuple[int, int]] = set()
    frames = [render_frame(backdrop, active, eaten) for _ in range(12)]
    columns = len(weeks)

    for row in range(7):
        direction = 1 if row % 2 == 0 else -1
        stops = list(range(0, columns, 2))
        if stops[-1] != columns - 1:
            stops.append(columns - 1)
        if direction < 0:
            stops.reverse()
        previous = -1 if direction > 0 else columns
        for col in stops:
            first, last = sorted((previous, col))
            newly_eaten = False
            for passed in range(max(0, first), min(columns - 1, last) + 1):
                key = (passed, row)
                if key in active and key not in eaten:
                    eaten.add(key)
                    newly_eaten = True
            frames.append(render_frame(backdrop, active, eaten, (col, row, direction), newly_eaten))
            previous = col
        for _ in range(2):
            frames.append(render_frame(backdrop, active, eaten, (stops[-1], row, direction)))

    frames.extend(render_frame(backdrop, active, eaten) for _ in range(9))
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=65,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"Rendered {len(frames)} frames to {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="mschr703")
    parser.add_argument("--output", type=Path, default=Path("contribution-game.gif"))
    parser.add_argument("--input", type=Path, help="Read a saved GitHub contribution calendar")
    args = parser.parse_args()
    calendar = json.loads(args.input.read_text(encoding="utf-8")) if args.input else fetch_calendar(args.username)
    weeks, active = prepare_grid(calendar)
    animate(weeks, active, args.output)


if __name__ == "__main__":
    main()
