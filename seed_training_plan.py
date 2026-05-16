"""
seed_training_plan.py — Populate ironman_training_plan in Supabase.

Generates the full periodized schedule from today's week through
2026-11-21 (Half Ironman) and upserts it into the Supabase table.

Safe to re-run: deletes existing rows then reinserts.

Usage:
    cd garmin-ai
    python seed_training_plan.py
"""

import os
import sys
import logging
from datetime import date

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    log.error("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    sys.exit(1)

from supabase import create_client
from training_plan import generate_full_plan, SCORE_MARATHON, MELAKA, BINTAN, IRONMAN

TABLE = "ironman_training_plan"
BATCH_SIZE = 100
RACE_DAYS = {
    SCORE_MARATHON.isoformat(),
    MELAKA.isoformat(),
    BINTAN.isoformat(),
    IRONMAN.isoformat(),
}


def main() -> None:
    db = create_client(SUPABASE_URL, SUPABASE_KEY)

    log.info("Generating full training plan …")
    rows = generate_full_plan()

    # Drop race days — athlete is racing, not training
    rows = [r for r in rows if r["date"] not in RACE_DAYS]

    log.info("  → %d sessions from %s to %s", len(rows), rows[0]["date"], rows[-1]["date"])

    # ── Phase summary ────────────────────────────────────────────────────────
    from collections import Counter
    phase_counts = Counter(r["phase"] for r in rows)
    disc_counts  = Counter(r["discipline"] for r in rows)
    log.info("  Phases:      %s", dict(phase_counts))
    log.info("  Disciplines: %s", dict(disc_counts))

    # ── Clear existing rows ──────────────────────────────────────────────────
    log.info("Clearing existing rows from %s …", TABLE)
    try:
        result = db.table(TABLE).select("id", count="exact").execute()
        existing = result.count or 0
        if existing > 0:
            log.info("  Deleting %d existing rows …", existing)
            db.table(TABLE).delete().neq("id", 0).execute()
        else:
            log.info("  Table is already empty.")
    except Exception as exc:
        log.error("Failed to clear table: %s", exc)
        sys.exit(1)

    # ── Insert in batches ────────────────────────────────────────────────────
    log.info("Inserting %d rows in batches of %d …", len(rows), BATCH_SIZE)
    inserted = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        try:
            db.table(TABLE).insert(batch).execute()
            inserted += len(batch)
            log.info("  [%d/%d] inserted", inserted, len(rows))
        except Exception as exc:
            log.error("  Batch %d failed: %s", i // BATCH_SIZE + 1, exc)
            # Print the first failing row to help diagnose schema mismatches
            if batch:
                log.error("  First row in failed batch: %s", batch[0])
            sys.exit(1)

    # ── Verify ───────────────────────────────────────────────────────────────
    result = db.table(TABLE).select("id", count="exact").execute()
    final_count = result.count or 0
    log.info("Done. %d rows now in %s.", final_count, TABLE)

    if final_count != len(rows):
        log.warning("Expected %d rows but found %d — check for errors above.", len(rows), final_count)


if __name__ == "__main__":
    main()
