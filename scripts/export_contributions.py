"""Export public GitHub contribution calendars for the interactive profile graph."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USERNAME = "mschr703"
OUTPUT = Path("docs/contributions.json")
API = "https://api.github.com/graphql"


def query_github(query: str, variables: dict) -> dict:
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GH_TOKEN is required")
    request = Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "mschr703-contribution-game",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"GitHub GraphQL returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError("Could not reach GitHub GraphQL") from exc
    if payload.get("errors"):
        raise RuntimeError("GitHub GraphQL rejected the contribution query")
    user = payload.get("data", {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub user {USERNAME!r} was not found")
    return user


def main() -> None:
    years_query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection { contributionYears }
      }
    }
    """
    years = query_github(years_query, {"login": USERNAME})["contributionsCollection"]["contributionYears"]
    current_year = datetime.now(timezone.utc).year
    years = sorted({year for year in years if year <= current_year})[-8:]
    if not years:
        years = [current_year]

    calendar_query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays { date contributionCount contributionLevel }
            }
          }
        }
      }
    }
    """
    calendars = {}
    for year in years:
        end = f"{year}-12-31T23:59:59Z"
        if year == current_year:
            end = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        user = query_github(
            calendar_query,
            {"login": USERNAME, "from": f"{year}-01-01T00:00:00Z", "to": end},
        )
        calendar = user["contributionsCollection"]["contributionCalendar"]
        days = [
            {
                "date": day["date"],
                "count": day["contributionCount"],
                "level": day["contributionLevel"],
            }
            for week in calendar["weeks"]
            for day in week["contributionDays"]
            if day["date"].startswith(str(year))
        ]
        calendars[str(year)] = {
            "total": calendar["totalContributions"],
            "days": days,
        }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps({"username": USERNAME, "years": calendars}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Exported {len(calendars)} contribution years to {OUTPUT}")


if __name__ == "__main__":
    main()
