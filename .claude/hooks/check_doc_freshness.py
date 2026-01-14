#!/usr/bin/env python3
"""
Doc Freshness Check Hook for Claude Code

Fires on SessionStart (including after compaction).
Checks if PROJECT_MEMORY.md is stale vs PROJECT_STATUS.md (>30 min).
Outputs context to agent if check fails.

Configure via env vars:
    DOC_STATUS_FILE: Path to status file (default: docs/PROJECT_STATUS.md)
    DOC_MEMORY_FILE: Path to memory file (default: docs/PROJECT_MEMORY.md)
    DOC_FRESHNESS_MINS: Tolerance in minutes (default: 30)
"""

import os
import sys
from pathlib import Path

def main():
    # Get project root from Claude's env var or current dir
    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))

    # Configurable paths
    status_path = os.environ.get("DOC_STATUS_FILE", "docs/PROJECT_STATUS.md")
    memory_path = os.environ.get("DOC_MEMORY_FILE", "docs/PROJECT_MEMORY.md")
    threshold_mins = int(os.environ.get("DOC_FRESHNESS_MINS", "30"))

    status_file = project_dir / status_path
    memory_file = project_dir / memory_path

    # Exit silently if files don't exist
    if not status_file.exists() or not memory_file.exists():
        sys.exit(0)

    # Get modification times
    status_mtime = status_file.stat().st_mtime
    memory_mtime = memory_file.stat().st_mtime

    # Calculate difference in minutes
    diff_mins = int((status_mtime - memory_mtime) / 60)

    # If STATUS is more recent than MEMORY by >threshold, emit context
    if diff_mins > threshold_mins:
        print(f"""
================================================================================
DOCUMENTATION FRESHNESS ALERT
================================================================================

PROJECT_STATUS.md was updated {diff_mins} minutes after PROJECT_MEMORY.md.

This indicates the previous session may not have documented their work.
Before starting, you MUST:

1. Run: python scripts/doctor.py
2. If check 7 fails, update docs/PROJECT_MEMORY.md with session notes
3. Then proceed with your work

Battle Rhythm reminder: After completing work, update BOTH files.
================================================================================
""")

    # Always exit 0 - we're adding context, not blocking
    sys.exit(0)

if __name__ == "__main__":
    main()
