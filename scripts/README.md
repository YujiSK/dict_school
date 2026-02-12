# scripts

Utility scripts that keep `terms.json` consistent.

## audit_terms.py

### Purpose
- Validate `terms.json` for duplicate Japanese / Portuguese entries
- Flag likely `type` misclassifications (term / phrase / sentence)
- Generate `search.ja` / `search.pt` arrays so the front-end search logic stays consistent

### Usage
```bash
cd c:/Python/dict_school
C:/Python/dict_school/.venv/Scripts/python.exe scripts/audit_terms.py --check
C:/Python/dict_school/.venv/Scripts/python.exe scripts/audit_terms.py --fix
```

### Output examples
```
DUPLICATE_JA:
T0005 <-> T0048

TYPE_MISMATCH:
- T0023 expected=phrase current=term

TERMS needing search update: 42
```

### Workflow
1. Run `--check` before making data edits. Resolve duplicates / mismatches manually if they appear.
2. Run `--fix` to regenerate the `search` arrays (this rewrites `terms.json`).
3. Inspect the diff, commit, and open a PR.
4. CI / reviewers run `--check` again; it should exit cleanly when data is consistent.
