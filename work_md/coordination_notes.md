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
