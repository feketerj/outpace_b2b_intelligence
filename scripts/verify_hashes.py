#!/usr/bin/env python3
"""
DACE v1.7.8 - Hash Verification (OG6 Gate)
Verifies integrity_hash for all JSON artifacts and manifest-tracked files.

Usage:
    python verify_hashes.py [artifacts_directory]

Default: ./artifacts

Exit Codes:
    0 - All hashes valid (OG6 PASS)
    1 - Hash verification failed (OG6 FAIL - ORCH-007)
    2 - Directory not found or other error

Supports:
    - JSON files: Verifies embedded integrity_hash
    - PRD.md: Verifies output_hash in metadata
    - All other files: Verifies against hash_manifest.json
"""
import hashlib
import json
import sys
from pathlib import Path

# Files to exclude from manifest verification
EXCLUDED_FILES = {'hash_manifest.json'}
MANIFEST_METADATA_KEYS = {'manifest_version', 'created', 'updated', 'artifacts'}


def compute_sha256(content: str) -> str:
    """Compute SHA256 hash of string content."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def compute_file_hash(filepath: Path) -> str:
    """Compute SHA256 hash of raw file bytes."""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def verify_json_integrity(filepath: Path) -> tuple[bool, str, str, str]:
    """
    Verify integrity hash of a JSON module.
    
    Returns: (passed: bool, status: str, claimed: str, computed: str)
    """
    try:
        data = json.loads(filepath.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        return False, "INVALID_JSON", str(e)[:20], "N/A"
    except Exception as e:
        return False, "READ_ERROR", str(e)[:20], "N/A"
    
    claimed = data.get('integrity_hash', None)
    
    if claimed is None:
        return False, "MISSING", "N/A", "N/A"
    
    if claimed == 'PENDING':
        return False, "PENDING", "PENDING", "Run hash_inserter.py first"
    
    # Compute hash excluding integrity_hash field
    content = {k: v for k, v in data.items() if k != 'integrity_hash'}
    json_str = json.dumps(content, sort_keys=True, separators=(',', ':'))
    computed = compute_sha256(json_str)
    
    if claimed == computed:
        return True, "VALID", claimed[:16] + '...', computed[:16] + '...'
    else:
        return False, "MISMATCH", claimed[:16] + '...', computed[:16] + '...'


def verify_prd_output_hash(filepath: Path) -> tuple[bool, str, str, str]:
    """
    Verify PRD.md output_hash matches body content.
    
    Returns: (passed: bool, status: str, claimed: str, computed: str)
    """
    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception as e:
        return False, "READ_ERROR", str(e)[:20], "N/A"
    
    # Extract output_hash from metadata
    claimed = None
    for line in content.split('\n'):
        if line.strip().startswith('output_hash:'):
            claimed = line.split(':', 1)[1].strip()
            break
    
    if claimed is None:
        return False, "MISSING", "N/A", "N/A"
    
    if claimed == 'PENDING':
        return False, "PENDING", "PENDING", "Run hash_inserter.py first"
    
    # Split to get body (after second ---)
    parts = content.split('---')
    if len(parts) < 3:
        return False, "PARSE_ERROR", claimed[:16] + '...' if claimed else "N/A", "Invalid structure"
    
    body = '---'.join(parts[2:]).strip()
    computed = compute_sha256(body)
    
    if claimed == computed:
        return True, "VALID", claimed[:16] + '...', computed[:16] + '...'
    else:
        return False, "MISMATCH", claimed[:16] + '...', computed[:16] + '...'


def verify_manifest_file(filepath: Path, claimed_hash: str) -> tuple[bool, str, str, str]:
    """
    Verify a file against its claimed hash from manifest.

    Returns: (passed: bool, status: str, claimed: str, computed: str)
    """
    if not filepath.exists():
        return False, "MISSING_FILE", claimed_hash[:16] + '...', "File not found"

    computed = compute_file_hash(filepath)

    if claimed_hash == computed:
        return True, "VALID", claimed_hash[:16] + '...', computed[:16] + '...'
    else:
        return False, "MISMATCH", claimed_hash[:16] + '...', computed[:16] + '...'


def main():
    # Determine artifacts directory
    if len(sys.argv) > 1:
        artifacts_dir = Path(sys.argv[1])
    else:
        artifacts_dir = Path('./artifacts')

    if not artifacts_dir.exists():
        print(f"[ERROR] Directory not found: {artifacts_dir}")
        sys.exit(2)

    print("=" * 70)
    print("DACE v1.7.8 - OG6 Hash Verification")
    print("=" * 70)
    print(f"\nVerifying: {artifacts_dir.absolute()}\n")

    all_passed = True
    results = []

    # Verify PRD.md if exists
    prd_path = artifacts_dir / 'PRD.md'
    if prd_path.exists():
        passed, status, claimed, computed = verify_prd_output_hash(prd_path)
        results.append(('PRD.md', passed, status, claimed, computed))
        if not passed:
            all_passed = False

    # Verify all JSON files (except manifest)
    json_files = sorted(artifacts_dir.glob('*.json'))

    for filepath in json_files:
        if filepath.name in EXCLUDED_FILES:
            continue
        passed, status, claimed, computed = verify_json_integrity(filepath)
        results.append((filepath.name, passed, status, claimed, computed))
        if not passed:
            all_passed = False

    # Verify files in hash_manifest.json
    manifest_path = artifacts_dir / 'hash_manifest.json'
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            if isinstance(manifest, dict) and isinstance(manifest.get('artifacts'), list):
                for index, entry in enumerate(manifest['artifacts']):
                    if not isinstance(entry, dict):
                        results.append(
                            (f"manifest_entry_{index}", False, "INVALID_ENTRY", "N/A", "N/A")
                        )
                        all_passed = False
                        continue
                    filename = entry.get('path')
                    claimed_hash = entry.get('sha256')
                    if not filename or not claimed_hash:
                        results.append(
                            (f"manifest_entry_{index}", False, "INVALID_ENTRY", "N/A", "N/A")
                        )
                        all_passed = False
                        continue
                    filepath = artifacts_dir / filename
                    passed, status, claimed, computed = verify_manifest_file(filepath, claimed_hash)
                    results.append((filename, passed, status, claimed, computed))
                    if not passed:
                        all_passed = False
            elif isinstance(manifest, dict):
                for filename, claimed_hash in sorted(manifest.items()):
                    if filename in MANIFEST_METADATA_KEYS:
                        continue
                    if not isinstance(claimed_hash, str):
                        results.append((filename, False, "INVALID_ENTRY", "N/A", "N/A"))
                        all_passed = False
                        continue
                    filepath = artifacts_dir / filename
                    passed, status, claimed, computed = verify_manifest_file(filepath, claimed_hash)
                    results.append((filename, passed, status, claimed, computed))
                    if not passed:
                        all_passed = False
        except json.JSONDecodeError as e:
            results.append(('hash_manifest.json', False, 'INVALID_JSON', str(e)[:16], 'N/A'))
            all_passed = False

    if not results:
        print("[WARNING] No artifacts found to verify")
        sys.exit(0)

    # Print results table
    print("-" * 70)
    print(f"{'File':<35} {'Status':<10} {'Claimed':<12} {'Computed':<12}")
    print("-" * 70)

    for filename, passed, status, claimed, computed in results:
        # Truncate long filenames
        display_name = filename[:33] + '..' if len(filename) > 35 else filename

        if passed:
            mark = "[OK]"
        elif status == "PENDING":
            mark = "[!!]"
        else:
            mark = "[FAIL]"

        print(f"{display_name:<35} {mark:<10} {claimed:<12} {computed:<12}")

    print("-" * 70)

    # Summary
    passed_count = sum(1 for r in results if r[1])
    total_count = len(results)

    if all_passed:
        print(f"\n[SUCCESS] {passed_count}/{total_count} artifacts verified. OG6 PASSED.")
        print("Ready for next agent.")
        sys.exit(0)
    else:
        failed = [r[0] for r in results if not r[1]]
        print(f"\n[FAILURE] {passed_count}/{total_count} verified. OG6 FAILED - ORCH-007.")
        print(f"Failed artifacts: {', '.join(failed)}")
        print("\nResolution:")
        print("  1. Run hash_inserter.py to compute hashes")
        print("  2. If still failing, artifact content may have been modified")
        print("  3. Re-run the agent that produced the artifact")
        sys.exit(1)


if __name__ == '__main__':
    main()
