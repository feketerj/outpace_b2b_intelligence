#!/usr/bin/env python3
"""
DACE v1.7.8 - Phase Locking Script (FIXED)
Copies verified artifacts to artifacts_locked/phase_N/ and updates Claude permissions.

FIX: Robust JSON parsing with BOM handling
"""
import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


PHASE_OUTPUTS = {
    1: {"artifacts": ["PRD.md"], "reports": []},
    2: {"artifacts": ["requirements_protocol.json", "requirements_product_core.json", "requirements_backend.json", "requirements_ui.json", "requirements_data.json", "requirements_nonfunctional.json", "requirements_acceptance.json", "requirements_verification.json", "resources_manifest.json"], "reports": []},
    3: {"artifacts": [], "reports": ["asset_validation.json"]},
    4: {"artifacts": ["harmonized_requirements_protocol.json", "harmonized_requirements_product_core.json", "harmonized_requirements_backend.json", "harmonized_requirements_ui.json", "harmonized_requirements_data.json", "harmonized_requirements_nonfunctional.json", "harmonized_requirements_acceptance.json", "harmonized_requirements_verification.json", "harmonized_resources_manifest.json"], "reports": ["terminology_harmonization.json"]},
    5: {"artifacts": ["stack_recommendations.json"], "reports": ["stack_selection.json"]},
    6: {"artifacts": ["requirements_protocol.json"], "reports": ["protocol_specification.json"]},
    7: {"artifacts": ["contracts.json"], "reports": []},
    8: {"artifacts": ["stack.json"], "reports": ["stack_specification.json"]},
    9: {"artifacts": ["tasks.json"], "reports": ["task_decomposition.json"]},
    10: {"artifacts": ["testing_strategy.json"], "reports": ["testing_strategy.json"]},
    11: {"artifacts": ["traceability_matrix.json"], "reports": ["traceability_matrix.json"]},
    12: {"artifacts": ["scaffold_manifest.json", "chunk_1_framework.py", "chunk_2_artifacts.py", "chunk_3_validation.py", "assemble_scaffold.py", "scaffold.py"], "reports": ["scaffold_manifest.json"]},
    13: {"artifacts": [], "reports": ["quality_gates.json"]},
    14: {"artifacts": ["repo_manifest.json"], "reports": ["repo_manifest.json"]}
}


def read_json_robust(file_path):
    raw_bytes = file_path.read_bytes()
    if raw_bytes.startswith(b'\xef\xbb\xbf'):
        raw_bytes = raw_bytes[3:]
    elif raw_bytes.startswith(b'\xff\xfe'):
        raw_bytes = raw_bytes[2:]
    elif raw_bytes.startswith(b'\xfe\xff'):
        raw_bytes = raw_bytes[2:]
    text = raw_bytes.decode('utf-8')
    return json.loads(text)


def write_json_clean(file_path, data):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def update_claude_permissions(settings_path, locked_dir):
    if not settings_path.exists():
        settings = {"permissions": {"allow": ["Bash(*)", "Read(*)", "Write(artifacts/*)", "Write(reports/*)", "Write(run_log.json)", "Edit(artifacts/*)", "Edit(reports/*)"], "deny": [], "ask": []}}
    else:
        try:
            settings = read_json_robust(settings_path)
        except Exception as e:
            print(f"[ERROR] Failed to read {settings_path}: {e}")
            return False
    if "permissions" not in settings:
        settings["permissions"] = {"allow": [], "deny": [], "ask": []}
    if "deny" not in settings["permissions"]:
        settings["permissions"]["deny"] = []
    deny_rules = ["Write(artifacts_locked/*)", "Edit(artifacts_locked/*)"]
    for rule in deny_rules:
        if rule not in settings["permissions"]["deny"]:
            settings["permissions"]["deny"].append(rule)
    try:
        write_json_clean(settings_path, settings)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to write {settings_path}: {e}")
        return False


def lock_phase(phase, artifacts_dir, reports_dir, locked_base, settings_path):
    if phase not in PHASE_OUTPUTS:
        print(f"[ERROR] Unknown phase: {phase}")
        return False
    phase_config = PHASE_OUTPUTS[phase]
    locked_dir = locked_base / f"phase_{phase}"
    print("=" * 60)
    print(f"DACE v1.7.8 - Locking Phase {phase}")
    print("=" * 60)
    print(f"\nTarget: {locked_dir}\n")
    locked_dir.mkdir(parents=True, exist_ok=True)
    copied_count = 0
    missing = []
    for filename in phase_config["artifacts"]:
        src = artifacts_dir / filename
        dst = locked_dir / filename
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  [LOCKED] {filename}")
            copied_count += 1
        else:
            missing.append(f"artifacts/{filename}")
    for filename in phase_config["reports"]:
        src = reports_dir / filename
        dst = locked_dir / filename
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  [LOCKED] {filename}")
            copied_count += 1
        else:
            missing.append(f"reports/{filename}")
    if missing:
        print(f"\n[WARNING] Missing files:")
        for f in missing:
            print(f"  - {f}")
    manifest = {"phase": phase, "locked_at": datetime.now().isoformat() + "Z", "files": phase_config["artifacts"] + phase_config["reports"], "copied": copied_count, "missing": missing}
    manifest_path = locked_dir / "_lock_manifest.json"
    write_json_clean(manifest_path, manifest)
    print(f"\n  [MANIFEST] _lock_manifest.json")
    print(f"\n[PERMISSIONS] Updating {settings_path}...")
    if update_claude_permissions(settings_path, str(locked_base)):
        print("  [OK] Deny rules added for artifacts_locked/*")
    else:
        print("  [WARN] Failed to update permissions")
    print("\n" + "-" * 60)
    print(f"Phase {phase} locked: {copied_count} files copied")
    if missing:
        print(f"[WARNING] {len(missing)} files missing")
    print("-" * 60)
    return len(missing) == 0


def main():
    parser = argparse.ArgumentParser(description="Lock DACE phase artifacts")
    parser.add_argument("phase", type=int, help="Phase number (1-14)")
    parser.add_argument("--artifacts-dir", type=Path, default=Path("./artifacts"))
    parser.add_argument("--reports-dir", type=Path, default=Path("./reports"))
    parser.add_argument("--locked-dir", type=Path, default=Path("./artifacts_locked"))
    parser.add_argument("--settings", type=Path, default=Path("./.claude/settings.local.json"))
    args = parser.parse_args()
    success = lock_phase(args.phase, args.artifacts_dir, args.reports_dir, args.locked_dir, args.settings)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()