# Proof Storage Documentation

This directory contains immutable proof records for test certifications, audits, and compliance verification.

## What Constitutes a Proof Packet

A proof packet is a collection of artifacts that provide verifiable evidence of a test certification or audit. Each packet contains:

1. **Evidence Packet** (`*_EVIDENCE_PACKET_*.md`)
   - Human-readable certification record
   - Test parameters and environment details
   - Pass/fail summary with confidence level
   - Reproduction instructions

2. **Artifact Index** (`*_ARTIFACT_INDEX.json`)
   - Machine-readable registry of all artifacts
   - SHA256 hashes for integrity verification
   - Metadata for automated processing

3. **Referenced Artifacts** (stored in source directories)
   - Raw log files (in `mc_reports/` or similar)
   - Report JSONs (in `carfax_reports/`)
   - These are NOT duplicated here; only hashes are stored

## Hash Verification Process

All artifacts are integrity-protected using SHA256 hashes. To verify:

### Windows (PowerShell)
```powershell
Get-FileHash <artifact_path> -Algorithm SHA256
```

### Linux/WSL/Git Bash
```bash
sha256sum <artifact_path>
```

### Verification Steps
1. Locate the artifact path in the `*_ARTIFACT_INDEX.json`
2. Run the appropriate hash command for your platform
3. Compare the output hash against the `sha256` field in the index
4. If hashes match, the artifact is verified as authentic

## Retention Policy

| Artifact Type | Retention Period | Storage Location |
|---------------|------------------|------------------|
| Evidence Packets | Permanent | `docs/proof/` |
| Artifact Indexes | Permanent | `docs/proof/` |
| Monte Carlo Logs | 90 days minimum | `mc_reports/` |
| Carfax Reports | 90 days minimum | `carfax_reports/` |

**Rules:**
- Evidence packets and artifact indexes are IMMUTABLE once committed
- Never modify a committed proof record; create a new one with updated date
- Large binary/log files stay in their source directories
- Only hashes and excerpts are stored in proof documents

## How to Add New Proofs

### Step 1: Complete the Certification Run
Run the full test suite with Monte Carlo validation:
```bash
# Example: 59 iterations for 95% confidence
API_URL="http://127.0.0.1:8000" bash carfax.sh all
```

### Step 2: Collect Artifact Hashes
```bash
sha256sum mc_reports/<log_file>.log
sha256sum carfax_reports/<report_file>.json
```

### Step 3: Create Evidence Packet
Create `docs/proof/<TEST_ID>_EVIDENCE_PACKET_<DATE>.md` with:
- Test ID and date
- Iteration counts (attempted/passed/failed)
- Confidence level achieved
- Environment details
- Artifact hashes
- Reproduction instructions

### Step 4: Create Artifact Index
Create `docs/proof/<TEST_ID>_ARTIFACT_INDEX.json` with:
- Machine-readable metadata
- Full artifact paths relative to repo root
- SHA256 hashes
- Environment configuration

### Step 5: Validate and Commit
```bash
# Validate JSON
python -c "import json; json.load(open('docs/proof/<TEST_ID>_ARTIFACT_INDEX.json'))"

# Check no large files
git diff --stat

# Commit
git add docs/proof/
git commit -m "feat(proof): add <TEST_ID> certification record"
```

## Naming Conventions

| File Type | Pattern | Example |
|-----------|---------|---------|
| Evidence Packet | `<TEST_ID>_EVIDENCE_PACKET_<YYYYMMDD>.md` | `TH-MC-003_EVIDENCE_PACKET_20251225.md` |
| Artifact Index | `<TEST_ID>_ARTIFACT_INDEX.json` | `TH-MC-003_ARTIFACT_INDEX.json` |

## Test ID Registry

| Test ID | Description | Confidence Target |
|---------|-------------|-------------------|
| TH-MC-001 | Initial Monte Carlo baseline | 95% (59 runs) |
| TH-MC-002 | Post-fix regression validation | 95% (59 runs) |
| TH-MC-003 | Harness stability certification | 95% (59 runs) |

## Contact

For questions about proof records or verification failures, consult the project maintainers or review `docs/verification_contract.md`.
