"""Import historical F1 data (2018 → current available season) using the existing DataAgent.

Run from the backend directory:
    python -m scripts.import_historical_data

Season discovery:
  - Start year: 2018 (earliest season with full FastF1 support).
  - End year  : current calendar year, probed automatically.
  - If a season returns no races from FastF1 (not yet released / future),
    it is silently skipped — nothing is recorded as a failure.

Per-season logic:
  1. Check whether race_results already exist for that season.
     → If yes, skip all three steps and move on.
  2. Fetch race schedule   – upserts Circuit + Race rows.
     → If 0 races returned, season is unavailable — skip gracefully.
  3. Fetch race results    – upserts Driver, Constructor, and RaceResult rows.
  4. Fetch qualifying      – upserts QualifyingResult rows.

Network resilience:
  - Telemetry loading is disabled (we need results, not lap-by-lap car data).
  - Steps that hit network errors are retried up to MAX_RETRIES times with
    exponential back-off before being recorded as failures.

Progress is printed after every season so you always know where you are
even if the script is interrupted.
"""

from __future__ import annotations

import datetime
import logging
import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable

import fastf1
from requests.exceptions import ChunkedEncodingError
from requests.exceptions import ConnectionError as RequestsConnectionError
from urllib3.exceptions import IncompleteRead, ProtocolError
from sqlalchemy import func, select

from app.agents.data_agent import DataAgent
from app.database.db import SessionLocal
from app.database.init_db import init_db
from app.models.circuit import Circuit
from app.models.constructor import Constructor
from app.models.driver import Driver
from app.models.qualifying_result import QualifyingResult
from app.models.race import Race
from app.models.race_result import RaceResult


# ── Season discovery ─────────────────────────────────────────────────────────

START_SEASON = 2018  # earliest season with full FastF1 data


def _current_season() -> int:
    """Return the current calendar year (= highest year we will try to import)."""
    return datetime.date.today().year


def _build_seasons() -> list[int]:
    """Return every season from START_SEASON up to and including the current year."""
    return list(range(START_SEASON, _current_season() + 1))


SEASONS: list[int] = _build_seasons()


# ── ANSI color helpers ────────────────────────────────────────────────────────

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_CYAN   = "\033[36m"
_RED    = "\033[31m"
_BLUE   = "\033[34m"
_DIM    = "\033[2m"


def _supports_color() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _c(text: str, *codes: str) -> str:
    if not _supports_color():
        return text
    return "".join(codes) + text + _RESET


def _banner(text: str) -> None:
    width = 64
    line  = "─" * width
    print()
    print(_c(line, _CYAN))
    print(_c(f"  {text}", _BOLD, _CYAN))
    print(_c(line, _CYAN))


def _step(label: str, detail: str = "") -> None:
    prefix = _c("  ▸", _YELLOW)
    suffix = _c(f" {detail}", _DIM) if detail else ""
    print(f"{prefix} {label}{suffix}")


def _ok(label: str, count: int, elapsed: float) -> None:
    tick  = _c("  ✓", _GREEN)
    cnt   = _c(str(count), _BOLD)
    secs  = _c(f"{elapsed:.1f}s", _DIM)
    print(f"{tick} {label}: {cnt} rows  ({secs})")


def _skip(label: str, reason: str) -> None:
    icon = _c("  ⊘", _BLUE)
    msg  = _c(reason, _DIM)
    print(f"{icon} {_c(label, _BLUE)}  —  {msg}")


def _warn(label: str, msg: str) -> None:
    print(_c(f"  ⚠  {label}: {msg}", _YELLOW))


def _err(label: str, msg: str) -> None:
    print(_c(f"  ✗  {label}: {msg}", _RED))


# ── Season outcome enum ───────────────────────────────────────────────────────

class Outcome(Enum):
    IMPORTED = auto()
    SKIPPED  = auto()
    FAILED   = auto()


# ── Per-season stats ──────────────────────────────────────────────────────────

@dataclass
class SeasonStats:
    season:     int
    outcome:    Outcome = Outcome.IMPORTED
    schedules:  int = 0
    results:    int = 0
    qualifying: int = 0
    errors:     list[str] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return bool(self.errors)


# ── Check whether a season is already imported ────────────────────────────────

def _season_result_count(year: int) -> int:
    """Return the number of race_results rows that exist for *year*."""
    with SessionLocal() as db:
        return db.scalar(
            select(func.count(RaceResult.id))
            .join(Race, RaceResult.race_id == Race.id)
            .where(Race.season == year)
        ) or 0


def _season_is_complete(year: int) -> bool:
    """Return True when race_results already exist for *year*."""
    return _season_result_count(year) > 0


# ── Network error types that trigger a retry ─────────────────────────────────

_RETRYABLE = (
    ChunkedEncodingError,
    IncompleteRead,
    ProtocolError,
    RequestsConnectionError,
    TimeoutError,
    OSError,
)

# Maximum attempts per step (1 original + 2 retries)
MAX_RETRIES = 3
# Back-off base in seconds: attempt 1 → 10 s, attempt 2 → 20 s
RETRY_BASE_DELAY = 10


# ── FastF1 telemetry patch ────────────────────────────────────────────────────

def _patch_fastf1_no_telemetry() -> None:
    """Monkey-patch Session.load so telemetry is never fetched.

    We only need session.results (finishing positions, points, status) which
    FastF1 fetches from the Ergast mirror.  The telemetry endpoints return
    files that are 5–50 MB each and time out on slow or rate-limited
    connections, causing IncompleteRead / ChunkedEncodingError.

    Disabling telemetry (and weather / messages which are also unnecessary)
    cuts the per-race download from ~50 MB to ~1 MB and eliminates the error.
    """
    _original_load = fastf1.core.Session.load

    def _load_no_telemetry(self, *args, **kwargs):  # noqa: ANN001
        kwargs.setdefault("telemetry", False)
        kwargs.setdefault("weather", False)
        kwargs.setdefault("messages", False)
        return _original_load(self, *args, **kwargs)

    fastf1.core.Session.load = _load_no_telemetry  # type: ignore[method-assign]
    LOGGER.info("FastF1 telemetry loading disabled — results-only mode active")


LOGGER = logging.getLogger(__name__)


# ── Single-step runner with retry ─────────────────────────────────────────────

def _run_step(label: str, fn: Callable[[], list]) -> tuple[int, list[str]]:
    """Execute *fn* with up to MAX_RETRIES attempts on network errors.

    Returns (row_count, error_list).  On retryable network failures the step
    waits RETRY_BASE_DELAY * attempt seconds before trying again.  Non-network
    exceptions are recorded immediately without retrying.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        t0 = time.perf_counter()
        try:
            rows    = fn()
            elapsed = time.perf_counter() - t0
            _ok(label, len(rows), elapsed)
            return len(rows), []

        except _RETRYABLE as exc:
            elapsed = time.perf_counter() - t0
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * attempt
                _warn(
                    label,
                    f"Network error on attempt {attempt}/{MAX_RETRIES} "
                    f"({type(exc).__name__}). Retrying in {delay}s…",
                )
                time.sleep(delay)
            else:
                msg = f"{type(exc).__name__}: {exc}"
                _err(label, f"Failed after {MAX_RETRIES} attempts — {msg}")
                return 0, [f"{label}: {msg}"]

        except Exception as exc:  # noqa: BLE001 — non-network errors, no retry
            elapsed = time.perf_counter() - t0
            msg = str(exc)
            _err(label, msg)
            return 0, [f"{label}: {msg}"]

    return 0, []  # unreachable, satisfies type checker


# ── Per-season import ─────────────────────────────────────────────────────────

def import_season(agent: DataAgent, year: int) -> SeasonStats:
    """Check, then import all three data types for *year*. Return stats."""
    _banner(f"Season {year}")

    # ── Pre-flight check: already in DB? ─────────────────────────────────────
    existing = _season_result_count(year)
    if existing > 0 and year != _current_season():
        _skip(
            f"Season {year}",
            f"{existing} race results already in DB — skipping",
        )
        return SeasonStats(season=year, outcome=Outcome.SKIPPED)

    stats = SeasonStats(season=year, outcome=Outcome.IMPORTED)

    # 1. Schedule ─────────────────────────────────────────────────────────────
    _step("Importing race schedule", f"season={year}")
    count, errs = _run_step("Schedule", lambda: agent.fetch_season_schedule(year))
    stats.schedules = count

    # Unavailability guard: if FastF1 returned 0 races (season not released yet
    # or future year with no calendar published), skip gracefully.
    # Errors from this step are intentionally dropped — this is NOT a failure.
    if count == 0:
        reason = (
            errs[0].split(":", 1)[-1].strip()
            if errs
            else "no races found in FastF1 schedule"
        )
        _skip(f"Season {year}", f"unavailable — {reason}")
        stats.outcome = Outcome.SKIPPED
        return stats

    stats.errors.extend(errs)

    # 2. Race results ─────────────────────────────────────────────────────────
    _step("Importing race results", f"season={year}")
    count, errs = _run_step("Race results", lambda: agent.fetch_race_results(year))
    stats.results = count
    stats.errors.extend(errs)

    # 3. Qualifying results ───────────────────────────────────────────────────
    _step("Importing qualifying results", f"season={year}")
    count, errs = _run_step("Qualifying", lambda: agent.fetch_qualifying_results(year))
    stats.qualifying = count
    stats.errors.extend(errs)

    # Promote to FAILED only when every step returned errors (nothing was saved)
    if stats.errors and stats.results == 0 and stats.qualifying == 0:
        stats.outcome = Outcome.FAILED

    return stats



# ── Rolling progress line ─────────────────────────────────────────────────────

def _print_progress(done: list[SeasonStats], remaining: list[int]) -> None:
    """Print a one-line progress snapshot after each season finishes."""
    n_imp  = sum(1 for s in done if s.outcome == Outcome.IMPORTED)
    n_skip = sum(1 for s in done if s.outcome == Outcome.SKIPPED)
    n_fail = sum(1 for s in done if s.outcome == Outcome.FAILED)
    left   = len(remaining)

    parts = [
        _c(f"imported={n_imp}", _GREEN),
        _c(f"skipped={n_skip}", _BLUE),
        _c(f"failed={n_fail}", _RED if n_fail else _DIM),
        _c(f"remaining={left}", _DIM),
    ]
    print("  " + "  ".join(parts))


# ── Final summary table ───────────────────────────────────────────────────────

def _print_summary(all_stats: list[SeasonStats], total_elapsed: float) -> None:
    """Print a tabular summary with Imported / Skipped / Failed counts."""
    _banner("Import Summary")

    # Two separate format strings:
    #   hdr_col – used only for the header row (5 columns including Status)
    #   num_col – used for data rows (3 numeric columns only)
    hdr_col = "{:<8} {:<10} {:>10} {:>14} {:>13}"
    num_col = "{:>10} {:>14} {:>13}"

    header = hdr_col.format("Season", "Status", "Schedules", "Race Results", "Qualifying")
    print(_c(f"  {header}", _BOLD))
    print(_c(f"  {'─' * 58}", _DIM))

    imported, skipped, failed = [], [], []
    for s in all_stats:
        if s.outcome == Outcome.IMPORTED:
            status_str = _c("imported  ", _GREEN)
            imported.append(s)
        elif s.outcome == Outcome.SKIPPED:
            status_str = _c("skipped   ", _BLUE)
            skipped.append(s)
        else:
            status_str = _c("failed    ", _RED)
            failed.append(s)

        nums = num_col.format(s.schedules, s.results, s.qualifying)
        line = f"  {_c(str(s.season), _BOLD):<8} {status_str}{nums}"
        print(line)

    print(_c(f"  {'─' * 58}", _DIM))

    # Totals row (imported seasons only)
    tot_s = sum(s.schedules  for s in imported)
    tot_r = sum(s.results    for s in imported)
    tot_q = sum(s.qualifying for s in imported)
    nums  = num_col.format(tot_s, tot_r, tot_q)
    print(f"  {_c('TOTAL   ', _BOLD)}            {_c(nums, _BOLD)}")


    # Counts box
    print()
    counts = [
        (_c(str(len(imported)), _GREEN),  "Imported"),
        (_c(str(len(skipped)),  _BLUE),   "Skipped"),
        (_c(str(len(failed)),   _RED if failed else _DIM), "Failed"),
    ]
    for val, label in counts:
        print(f"    {val:>4}  {label}")

    # DB snapshot
    with SessionLocal() as db:
        def _count(model):  # noqa: ANN001
            return db.scalar(select(func.count()).select_from(model)) or 0

        print()
        print(_c("  Database row counts after import:", _DIM))
        for label, model in [
            ("races",              Race),
            ("race_results",       RaceResult),
            ("qualifying_results", QualifyingResult),
            ("circuits",           Circuit),
            ("drivers",            Driver),
            ("constructors",       Constructor),
        ]:
            print(f"    {label:<22} {_c(str(_count(model)), _BOLD)}")

    print()
    print(f"  Finished in {_c(f'{total_elapsed:.1f}s', _BOLD)}")

    if failed:
        print()
        _warn("Failed seasons", ", ".join(str(s.season) for s in failed))
        for s in failed:
            for msg in s.errors:
                print(_c(f"    • {msg}", _YELLOW))

    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    """Run the full historical data import with skip-if-complete logic."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("app.agents.data_agent").setLevel(logging.INFO)

    print(_c("\nRacecraft AI – Historical Data Import", _BOLD, _CYAN))
    print(_c(f"Seasons: {', '.join(str(y) for y in SEASONS)}", _DIM))
    print(_c("Seasons with existing race_results are skipped automatically.", _DIM))
    print(_c(f"Network retries: {MAX_RETRIES} attempts · back-off {RETRY_BASE_DELAY}s base\n", _DIM))

    # Patch FastF1 to skip telemetry before anything touches the API
    _patch_fastf1_no_telemetry()

    init_db()

    agent     = DataAgent()
    all_stats : list[SeasonStats] = []
    remaining = list(SEASONS)
    t_start   = time.perf_counter()

    for year in SEASONS:
        remaining.remove(year)
        stats = import_season(agent, year)
        all_stats.append(stats)

        # ── Save progress snapshot ────────────────────────────────────────────
        _print_progress(all_stats, remaining)

    total_elapsed = time.perf_counter() - t_start
    _print_summary(all_stats, total_elapsed)


if __name__ == "__main__":
    main()
