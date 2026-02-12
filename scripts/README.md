# scripts

Utility scripts that keep `terms.json` consistent.

## audit_terms.py

### Purpose
- Validate `terms.json` for duplicate JA/PT entries and structural corruption (ID/category issues)
- Regenerate deterministic `search.ja` / `search.pt` arrays for every term
- Recompute `type` using the v0.2 rules (term / phrase / sentence)

### Usage
```bash
cd c:/Python/dict_school
C:/Python/dict_school/.venv/Scripts/python.exe scripts/audit_terms.py --check
C:/Python/dict_school/.venv/Scripts/python.exe scripts/audit_terms.py --fix
```

### Deterministic generation rules
- `search.ja`: normalize (`NFKC`, trim, whitespace compression) → split on whitespace & punctuation (`/ , ・ () [] 「」 ...`) → remove empty tokens → de-duplicate → sort lexicographically.
- `search.pt`: normalize + lowercase → split on `[^a-z0-9]` → add both original tokens and accent-less variants → de-duplicate → sort.
- `type`: sentence if JA/PT contains `。？！!?` **or** either string is length ≥ 25. Otherwise phrase if JA contains any of `ください/お願いします/してください/しましょう/します/しません/できますか/してもいい/してはいけません`. Fallback to term.

### Status levels (generated report)
- **FAIL**: Structural issues (missing IDs, duplicate IDs, invalid categories, missing ja/pt) or when `search`/`type` need regeneration.
- **WARN**: Non-blocking data cleanups remain (e.g., duplicate PT strings) but structural health is OK.
- **PASS**: Clean dataset.

### Workflow
1. Run `--check` to understand the current status (report stored under `work_md/audit_reports/`).
2. Run `--fix` to regenerate `search` + `type`, then inspect the diff (only those fields should change).
3. Run `--check` again; expect PASS/WARN (WARN only for intentional PT duplicates like T0038/T0039).
4. Commit updated `terms.json` + reports + any documentation updates, then open a PR.
