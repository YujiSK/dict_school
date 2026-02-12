# Coordination Notes

## Nicknames
- Developer-facing AI assistant (me): **Rail**
- Secondary AI partner mentioned by the user: **Echo**

## Collaboration Principles
1. **Autonomy with accountability**: Rail can make reasonable implementation decisions based on the repository state without waiting for explicit confirmation unless the request clearly depends on the developer's unique preferences.
2. **Escalation criteria**: Only ask the developer when a decision:
   - Impacts product direction or UX philosophy the developer previously emphasized
   - Requires choosing between multiple conflicting requirements provided by the developer/Echo
   - Has irreversible consequences (e.g., deleting data, large-scale refactors)
3. **When escalation is needed**: present concrete options plus decision criteria so the developer can answer quickly.
4. **Documentation**: As key policies or workflows become clear, add/update Markdown files under `work_md/` so both Rail and Echo have a shared reference.

## Documentation Placement Rules
- `work_md/`: Strategy、仕様、運用ルールなど、Rail/Echo/開発者の共通理解に必要なMarkdownはすべてここに置く。
- 各ディレクトリ配下: 実装に密着したREADME（例: `scripts/README.md` や `web/README.md`）のみ、そのディレクトリに配置してよい。
- 新しいルールやテンプレートを追加したら、`work_md/` 内に Markdown を作成し、`coordination_notes.md` にリンクや概要を追記する。
- 監査レポート (`scripts/audit_terms.py --check/--fix`) は `work_md/audit_reports/` に Markdown で保存し、必要に応じてレスポンスで要約を共有する。

## Data Quality Rules (Issue #2)
- `search.ja` / `search.pt` は `scripts/audit_terms.py --fix` で全項目再生成し、差分があれば `terms.json` に書き込む。
- `type` 推論ルール（2026-02-12 改訂）:
   - `sentence`: `。？！!?` を含む、または 25 文字以上。
   - `phrase`: 上記以外で以下のいずれかを満たす場合 → `phrase`。
      - `ください` / `お願いします` / `します` / `しません` / `しますか` / `ませんか` を含む。
      - 空白/記号区切り（既存 `PHRASE_HINTS`）。
      - 12 文字以上。
   - `term`: それ以外。
- `--fix` が自動更新してよい項目は `search` と `type` のみ。カテゴリ/ID/translationなど他フィールドは触らない。
- PT 重複（例: T0038/T0039）は自動削除・統合しない。`--check` レポートで WARN として報告し続ける。

## Response Style Reminders
- Default to concise Japanese explanations unless instructions specify otherwise.
- Reference files and lines using repository-relative links per workspace rules.
- Summaries should state outcomes first, then next steps.

*(Update this file as collaboration rules evolve.)*

## Decisions – 2026-02-12
- **Role scope confirmed for Rail**: Proceed autonomously on implementation/refactoring/scripts/PR prep/local verification unless encountering irreversible decisions, long-term data-structure impacts, or unclear strategic direction. This keeps Issue #2 velocity high without waiting on Echo for routine execution work.
- **Assumptions**: Echo continues to own product priorities/design philosophy, and Beacon monitors structural drift, so Rail’s autonomy does not override those signals.
- **Risks**: Potential misalignment if strategic direction shifts silently; mitigation is to escalate promptly when requirements feel ambiguous or when work could affect shared data contracts.

## Worklog – Issue #2 (2026-02-12)
- Kickoff: Aligning scripts/audit_terms.py `--fix` + `--check` with v0.2 spec (deterministic `search` regeneration, simplified `type` rules, structural FAIL guards). Assumption: Existing term/category schema stays as in `terms.json`/`schema_v0.2.md`; only `search` + `type` mutate. Risk: Tokenization or new type heuristics could surface unexpected WARN spikes—will monitor post-`--check` report before shipping.
- Update 2: `--fix` now regenerates tokenized/lexicographically sorted `search` arrays and overwrites `type` with the new sentence/phrase heuristics; `--check` enforces structural guards (IDs, categories, ja/pt presence). Residual WARN intentionally limited to PT duplicate pair `[T0038, T0039]`. Next step after merging: shift to Issue #3 (sources ledger automation) while keeping audit script handy for regression checks.
- Update 3 (v0.2.1 hotfix): Trimmed report output to strictly follow `AUDIT_REPORT_SPEC.md` (no extra headings for structural stats) and forced UTF-8 stdout reconfiguration to stop Windows console `UnicodeEncodeError`s. Assumption: `sys.stdout.reconfigure` exists on all Python 3.7+ Windows builds; fallback is silently ignored if unavailable. Risk: Without the removed detail sections, investigating structural errors relies on Section 7 bullet text—acceptable for now per Beacon.
- Update 4 (Issue #3 MVP): Introduced `sources.json` v0.3 (IDs `S####`, required `title/type`, optional `url/note/accessed_at`) and added deterministic `term.sources` arrays mirroring `sourceRefs`. `audit_terms.py` now FAILs when the ledger is missing/invalid, IDs collide, required keys are absent, or terms reference unknown sources. WARN covers malformed URLs/date stamps plus currently unreferenced sources. `--fix` only backfills missing `sources: []` fields—no automatic provenance guessing.
- Update 4 (PR ready): Created PR [#4](https://github.com/YujiSK/dict_school/pull/4) – “Issue #2: Deterministic audit + v0.2.1 hotfix (spec/windows)”. Status: awaiting review; WARN limited to PT duplicate (T0038/T0039). Next action once merged: pivot to Issue #3 (sources ledger) per roadmap.
