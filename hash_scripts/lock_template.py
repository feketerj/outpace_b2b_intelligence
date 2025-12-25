"""
DACE v1.7.8.1 - Template Locking Script
Computes SHA256 hashes for all template files and creates a lock manifest.
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# Files to lock - organized by category
TEMPLATE_FILES = {
    "root_docs": [
        "README.md",
        "CLAUDE.md",
        "CLAUDE_MATERIALIZE.md",
        "Codeveloper_README_dace_1_7_8.md"
    ],
    "user_notes": [
        "user_notes/CODEVELOPER_PROMPT_v1_7_8_1.md",
        "user_notes/DACE_ADVISOR_SYSTEM_PROMPT.md",
        "user_notes/DACE_BUILD_PHASE_CHECKLIST.md",
        "user_notes/DACE_FIXER_AGENT.md",
        "user_notes/DACE_ORCHESTRATOR_PROMPT_GUIDE.md",
        "user_notes/DACE_ROLE_AND_REPO_MAP.md",
        "user_notes/DACE_SHELF_PROMPTS.md",
        "user_notes/DACE_SPEC_CHECKLIST.md",
        "user_notes/DACE_VISIBILITY_MANIFEST.md",
        "user_notes/NBLM_CONTINUITY_EXTRACTION_PROMPTS.md",
        "user_notes/prompt_engineering_meta_spec.json"
    ],
    "agent_specs": [
        "agent_0_orchestrator/AGENT_0_ORCHESTRATOR_v_1_7_8.md",
        "agent_1_prd_generation/AGENT_1_PRD_GENERATION_v_1_7_7.md",
        "agent_2_prd_ingestion/AGENT_2_PRD_INGESTION_v_1_7_7.md",
        "agent_3_asset_validation/AGENT_3_ASSET_VALIDATION_v_1_7_7.md",
        "agent_4_terminology_harmonization/AGENT_4_TERMINOLOGY_HARMONIZATION_v_1_7_7.md",
        "agent_5_stack_selection/AGENT_5_STACK_SELECTION_v_1_7_7.md",
        "agent_6_protocol_specification/AGENT_6_PROTOCOL_SPECIFICATION_v_1_7_7.md",
        "agent_7_contract_mapping/AGENT_7_CONTRACT_MAPPING_v_1_7_7.md",
        "agent_8_tech_stack_specs/AGENT_8_TECH_STACK_SPECS_v_1_7_7.md",
        "agent_9_task_decomposition/AGENT_9_TASK_DECOMPOSITION_v_1_7_7.md",
        "agent_10_testing_strategy/AGENT_10_TESTING_STRATEGY_v_1_7_7.md",
        "agent_11_traceability_matrix/AGENT_11_TRACEABILITY_MATRIX_v_1_7_7.md",
        "agent_12_scaffold_generation/AGENT_12_SCAFFOLD_GENERATION_v_1_7_7.md",
        "agent_13_quality_gates_validator/AGENT_13_QUALITY_GATES_VALIDATOR_v_1_7_7.md",
        "agent_14_repo_packager/AGENT_14_REPO_PACKAGER_v_1_7_7.md"
    ],
    "scripts": [
        "hash_scripts/hash_inserter.py",
        "hash_scripts/verify_hashes.py",
        "hash_scripts/lock_phase.py",
        "hash_scripts/validate_phase.py"
    ]
}


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    content = file_path.read_bytes()
    # Strip BOM if present
    if content.startswith(b'\xef\xbb\xbf'):
        content = content[3:]
    return hashlib.sha256(content).hexdigest()


def lock_template(base_path: Path) -> dict:
    """Lock all template files and return manifest."""
    manifest = {
        "version": "1.7.8.1",
        "locked_at": datetime.now().isoformat(),
        "categories": {},
        "files": {},
        "summary": {
            "total_files": 0,
            "locked": 0,
            "missing": 0,
            "errors": 0
        }
    }

    for category, files in TEMPLATE_FILES.items():
        manifest["categories"][category] = {
            "files": [],
            "status": "ok"
        }

        for file_rel in files:
            file_path = base_path / file_rel
            manifest["summary"]["total_files"] += 1
            file_entry: Dict[str, Any] = {
                "path": file_rel,
                "category": category
            }

            if not file_path.exists():
                file_entry["status"] = "MISSING"
                file_entry["hash"] = ""
                manifest["summary"]["missing"] += 1
                manifest["categories"][category]["status"] = "incomplete"
                print(f"  MISSING: {file_rel}")
            else:
                try:
                    file_entry["hash"] = compute_file_hash(file_path)
                    file_entry["status"] = "LOCKED"
                    file_entry["size_bytes"] = file_path.stat().st_size
                    manifest["summary"]["locked"] += 1
                    print(f"  LOCKED: {file_rel}")
                except Exception as e:
                    file_entry["status"] = "ERROR"
                    file_entry["hash"] = ""
                    file_entry["error"] = str(e)
                    manifest["summary"]["errors"] += 1
                    manifest["categories"][category]["status"] = "error"
                    print(f"  ERROR: {file_rel} - {e}")

            manifest["files"][file_rel] = file_entry
            manifest["categories"][category]["files"].append(file_rel)

    return manifest


def verify_template(base_path: Path, manifest_path: Path) -> bool:
    """Verify template files against lock manifest."""
    if not manifest_path.exists():
        print("ERROR: Lock manifest not found")
        return False

    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    all_valid = True
    verified = 0
    failed = 0

    print(f"\nVerifying against manifest from {manifest['locked_at']}")
    print("=" * 60)

    for file_rel, entry in manifest["files"].items():
        file_path = base_path / file_rel

        if entry["status"] == "MISSING":
            # Was already missing at lock time
            if not file_path.exists():
                print(f"  SKIP (was missing): {file_rel}")
            else:
                print(f"  NEW FILE (not in manifest): {file_rel}")
            continue

        if not file_path.exists():
            print(f"  FAIL (deleted): {file_rel}")
            all_valid = False
            failed += 1
            continue

        current_hash = compute_file_hash(file_path)
        if current_hash == entry["hash"]:
            print(f"  PASS: {file_rel}")
            verified += 1
        else:
            print(f"  FAIL (modified): {file_rel}")
            print(f"         Expected: {entry['hash'][:16]}...")
            print(f"         Got:      {current_hash[:16]}...")
            all_valid = False
            failed += 1

    print("=" * 60)
    print(f"Verified: {verified} | Failed: {failed}")

    return all_valid


def main():
    import argparse

    parser = argparse.ArgumentParser(description="DACE Template Locking")
    parser.add_argument("action", choices=["lock", "verify"], help="Action to perform")
    parser.add_argument("--path", default=".", help="Base path of template")
    parser.add_argument("--manifest", default="TEMPLATE_LOCK_MANIFEST.json", help="Manifest filename")

    args = parser.parse_args()
    base_path = Path(args.path).resolve()
    manifest_path = base_path / args.manifest

    print(f"DACE Template {'Locking' if args.action == 'lock' else 'Verification'}")
    print(f"Base path: {base_path}")
    print("=" * 60)

    if args.action == "lock":
        manifest = lock_template(base_path)

        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)

        print("=" * 60)
        print(f"Manifest written to: {manifest_path}")
        print(f"Total: {manifest['summary']['total_files']} | "
              f"Locked: {manifest['summary']['locked']} | "
              f"Missing: {manifest['summary']['missing']} | "
              f"Errors: {manifest['summary']['errors']}")

        if manifest['summary']['missing'] > 0 or manifest['summary']['errors'] > 0:
            print("\nWARNING: Some files could not be locked")
            return 1

        print("\nTemplate locked successfully")
        return 0

    else:  # verify
        if verify_template(base_path, manifest_path):
            print("\nTemplate verification PASSED")
            return 0
        else:
            print("\nTemplate verification FAILED")
            return 1


if __name__ == "__main__":
    exit(main())
