#!/usr/bin/env python3
"""Phase Deliverable Validator - DACE v1.7.8"""
import json
import sys
from pathlib import Path

def validate_phase_2():
    required_files = [
        "src/types/tokens.ts",
        "src/types/services.ts",
        "src/types/api.ts",
        "src/types/errors.ts",
        "src/types/index.ts"
    ]

    missing = []
    total_lines = 0

    for filepath in required_files:
        path = Path(filepath)
        if not path.exists():
            missing.append(filepath)
        else:
            lines = len(path.read_text().splitlines())
            total_lines += lines
            print(f"? {filepath} ({lines} lines)")

    if missing:
        print("\n MISSING FILES:")
        for f in missing:
            print(f"  - {f}")
        return False

    if total_lines < 2000:
        print(f"\n INSUFFICIENT: {total_lines} lines (min 2000)")
        return False

    print(f"\n PHASE 2 VALID: {total_lines} lines")
    return True

if __name__ == "__main__":
    phase = int(sys.argv[1])
    success = validate_phase_2() if phase == 2 else False
    sys.exit(0 if success else 1)
