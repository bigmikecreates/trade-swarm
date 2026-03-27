# Experiments — auto-cleanup job (run via cron)
#
# Add to crontab:
#   0 */6 * * * python /path/to/trade-swarm/lab/cleanup_job.py
#
# Runs every 6 hours. Deletes experiment directories older than CLEANUP_TTL_DAYS.
# Safe: only deletes experiment data, not config files or source code.

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from lab.config import lab_config
from lab.data.persistence.directory_store import DirectoryStore


def run_cleanup(ttl_days: int | None = None):
    ttl = ttl_days or lab_config.CLEANUP_TTL_DAYS
    store = DirectoryStore(lab_config.EXPERIMENTS_DIR)

    dirs = store.list_all_dirs()
    to_delete = [
        d for d in dirs
        if store.get_dir_age_days(d) > ttl
    ]

    if not to_delete:
        print(f"[{datetime.now()}] No directories older than {ttl} days.")
        return

    for d in to_delete:
        import shutil
        shutil.rmtree(d)
        print(f"[{datetime.now()}] Deleted: {d.name} ({store.get_dir_age_days(d):.1f} days old)")


if __name__ == "__main__":
    run_cleanup()
