"""Download public Chess.com monthly PGN archives.

This uses Chess.com's public API endpoints, not webpage scraping:

    https://api.chess.com/pub/player/{username}/games/archives
    https://api.chess.com/pub/player/{username}/games/{YYYY}/{MM}/pgn
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
import socket
from dataclasses import dataclass
from pathlib import Path


API_ROOT = "https://api.chess.com/pub/player"
USER_AGENT = "Xutrix-ChessEngine/0.1 (+training-data; contact: local)"


@dataclass(frozen=True)
class Month:
    year: int
    month: int

    @classmethod
    def parse(cls, text: str) -> "Month":
        try:
            year_text, month_text = text.split("-", 1)
            year = int(year_text)
            month = int(month_text)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("Use YYYY-MM format.") from exc
        if year < 2000 or not 1 <= month <= 12:
            raise argparse.ArgumentTypeError("Use a valid YYYY-MM month.")
        return cls(year, month)

    def key(self) -> tuple[int, int]:
        return (self.year, self.month)

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


def request_text(url: str, retries: int = 3, sleep_seconds: float = 1.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 404:
                raise
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            last_error = exc
        if attempt + 1 < retries:
            time.sleep(sleep_seconds * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def list_archive_months(username: str) -> list[Month]:
    url = f"{API_ROOT}/{username}/games/archives"
    payload = json.loads(request_text(url))
    months: list[Month] = []
    for archive_url in payload.get("archives", []):
        parts = archive_url.rstrip("/").split("/")
        if len(parts) < 2:
            continue
        try:
            months.append(Month(int(parts[-2]), int(parts[-1])))
        except ValueError:
            continue
    return sorted(months, key=Month.key)


def filter_months(months: list[Month], start: Month | None, end: Month | None, limit: int | None) -> list[Month]:
    selected = [
        month
        for month in months
        if (start is None or month.key() >= start.key())
        and (end is None or month.key() <= end.key())
    ]
    if limit is not None:
        selected = selected[-limit:]
    return selected


def download_month_pgn(username: str, month: Month) -> str:
    url = f"{API_ROOT}/{username}/games/{month.year:04d}/{month.month:02d}/pgn"
    return request_text(url)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download public Chess.com PGNs for one player.")
    parser.add_argument("--username", required=True, help="Chess.com username, e.g. Hikaru")
    parser.add_argument("--from", dest="start", type=Month.parse, help="First month, YYYY-MM")
    parser.add_argument("--to", dest="end", type=Month.parse, help="Last month, YYYY-MM")
    parser.add_argument("--limit-months", type=int, help="Keep only the most recent N matching months")
    parser.add_argument("--sleep", type=float, default=1.0, help="Seconds to sleep between monthly downloads")
    parser.add_argument("--skip-failed", action="store_true", help="Continue when a monthly archive times out/fails")
    parser.add_argument("--out", required=True, type=Path, help="Combined PGN output path")
    args = parser.parse_args()

    archive_months = list_archive_months(args.username)
    selected_months = filter_months(archive_months, args.start, args.end, args.limit_months)
    if not selected_months:
        raise SystemExit("No monthly archives matched the requested range.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    games_hint = 0
    with args.out.open("w", encoding="utf-8", newline="\n") as output:
        for index, month in enumerate(selected_months, start=1):
            print(f"[{index}/{len(selected_months)}] downloading {args.username} {month}")
            try:
                pgn = download_month_pgn(args.username, month)
            except Exception as exc:
                if not args.skip_failed:
                    raise
                print(f"warning: skipped {month}: {exc}")
                continue
            pgn = pgn.strip()
            if pgn:
                output.write(pgn)
                output.write("\n\n")
                downloaded += 1
                games_hint += pgn.count("[Event ")
            if index < len(selected_months):
                time.sleep(args.sleep)

    print(f"wrote {args.out}")
    print(f"months downloaded: {downloaded}")
    print(f"games detected: {games_hint}")


if __name__ == "__main__":
    main()
