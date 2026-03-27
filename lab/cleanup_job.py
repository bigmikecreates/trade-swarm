"""Experiments auto-cleanup job (run via cron).

Usage:
    python lab/cleanup_job.py                 # Use default TTL (5 days)
    python lab/cleanup_job.py --ttl 7         # Delete dirs older than 7 days
    python lab/cleanup_job.py --dry-run        # Preview what would be deleted

Add to crontab (runs every 6 hours):
    0 */6 * * * /home/bigmike/bigmike/git-projects/trade-swarm/.venv/bin/python /home/bigmike/bigmike/git-projects/trade-swarm/lab/cleanup_job.py >> /home/bigmike/bigmike/git-projects/trade-swarm/logs/cleanup.log 2>&1

Or use the Makefile:
    make cleanup TTL=5    # Delete directories older than 5 days
    make cleanup-dry TTL=5 # Preview directories older than 5 days

Safe: only deletes experiment data in lab/experiments/, not config files or source code.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lab.config import lab_config
from lab.data.persistence.directory_store import DirectoryStore

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def run_cleanup(ttl_days: int | None = None, dry_run: bool = False):
    """Clean up experiment directories older than TTL days.
    
    Args:
        ttl_days: Delete directories older than this many days (default: from config)
        dry_run: If True, only print what would be deleted without actually deleting
    """
    ttl = ttl_days or lab_config.CLEANUP_TTL_DAYS
    logger.info(f"Starting cleanup with TTL={ttl} days (dry_run={dry_run})")
    
    store = DirectoryStore(lab_config.EXPERIMENTS_DIR)
    
    dirs = store.list_all_dirs()
    to_delete = [
        d for d in dirs
        if store.get_dir_age_days(d) > ttl
    ]
    
    if not to_delete:
        logger.info(f"No directories older than {ttl} days found.")
        return
    
    logger.info(f"Found {len(to_delete)} directories to clean up:")
    
    for d in to_delete:
        age = store.get_dir_age_days(d)
        logger.info(f"  - {d.name} ({age:.1f} days old)")
    
    if dry_run:
        logger.info(f"Dry run - would delete {len(to_delete)} directories")
        return
    
    deleted = 0
    for d in to_delete:
        try:
            import shutil
            shutil.rmtree(d)
            logger.info(f"Deleted: {d.name}")
            deleted += 1
        except Exception as e:
            logger.error(f"Failed to delete {d.name}: {e}")
    
    logger.info(f"Cleanup complete - deleted {deleted}/{len(to_delete)} directories")


def main():
    parser = argparse.ArgumentParser(
        description="Clean up old experiment directories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--ttl", 
        type=int, 
        default=None,
        help=f"Delete directories older than N days (default: {lab_config.CLEANUP_TTL_DAYS})"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Preview what would be deleted without actually deleting"
    )
    
    args = parser.parse_args()
    run_cleanup(ttl_days=args.ttl, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
