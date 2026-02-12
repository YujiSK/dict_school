#!/usr/bin/env python3
"""Audit and maintenance utilities for terms.json."""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, List, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
TERMS_PATH = REPO_ROOT / "terms.json"
SOURCES_PATH = REPO_ROOT / "sources.json"
REPORT_ROOT = REPO_ROOT / "work_md" / "audit_reports"

JA_SENTENCE_TOKENS = "。？！!?"
JA_TOKEN_SPLIT_RE = re.compile(
    r"[\s、,，・·/／\\()（）\[\]{}【】「」『』<>\"'。、…~〜！？!?:;＋+\-]+"
)
PT_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")
SOURCE_ID_RE = re.compile(r"^S\d{4}$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PHRASE_KEYWORDS = [
    "ください",
    "お願いします",
    "してください",
    "しましょう",
    "します",
    "しません",
    "できますか",
    "してもいい",
    "してはいけません",
]


@dataclass
class FixStats:
    type_updates: int = 0
    search_updates: int = 0
    sources_added: int = 0
    terms_modified: int = 0
    json_modified: bool = False


def normalize_common(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch))


def normalize_ja(value: str | None) -> str:
    return normalize_common(value)


def normalize_pt(value: str | None) -> str:
    lowered = normalize_common(value).lower()
    return strip_accents(lowered)


def tokenize_pt(value: str | None) -> List[str]:
    normalized = normalize_common(value).lower()
    if not normalized:
        return []
    tokens = [token for token in PT_TOKEN_SPLIT_RE.split(normalized) if token]
    accentless = []
    for token in tokens:
        stripped = strip_accents(token)
        if stripped:
            accentless.append(stripped)
    combined = set(tokens + accentless)
    return sorted(combined)


def tokenize_ja(value: str | None) -> List[str]:
    normalized = normalize_common(value)
    if not normalized:
        return []
    tokens = [token for token in JA_TOKEN_SPLIT_RE.split(normalized) if token]
    return sorted(set(tokens))


def contains_sentence_punctuation(text: str) -> bool:
    return any(char in JA_SENTENCE_TOKENS for char in text)


def infer_type(ja_text: str, pt_text: str) -> str:
    if is_sentence(ja_text, pt_text):
        return "sentence"
    if contains_phrase_keyword(ja_text):
        return "phrase"
    return "term"


def type_reason(ja_text: str, pt_text: str) -> str:
    if is_sentence(ja_text, pt_text):
        if contains_sentence_punctuation(ja_text) or contains_sentence_punctuation(pt_text):
            return "Contains sentence-ending punctuation"
        return "Length >= 25 characters"
    if contains_phrase_keyword(ja_text):
        return "Contains predefined phrase keyword"
    return "Defaulted to term"


def contains_phrase_keyword(text: str) -> bool:
    return any(keyword in text for keyword in PHRASE_KEYWORDS)


def is_sentence(ja_text: str, pt_text: str) -> bool:
    if ja_text and contains_sentence_punctuation(ja_text):
        return True
    if pt_text and contains_sentence_punctuation(pt_text):
        return True
    max_length = max(len(ja_text), len(pt_text))
    return max_length >= 25


def build_search_payload(term: Dict) -> Dict[str, List[str]]:
    translations = term.get("translations") or {}
    pt_raw = translations.get("pt")
    return {
        "ja": tokenize_ja(term.get("ja")),
        "pt": tokenize_pt(pt_raw),
    }


def load_terms() -> Dict:
    if not TERMS_PATH.exists():
        raise FileNotFoundError(f"terms.json not found at {TERMS_PATH}")
    with TERMS_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_terms(payload: Dict) -> None:
    with TERMS_PATH.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def load_sources() -> Dict:
    if not SOURCES_PATH.exists():
        raise FileNotFoundError(f"sources.json not found at {SOURCES_PATH}")
    with SOURCES_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def detect_duplicates(terms: List[Dict], key_getter, value_getter) -> Dict[str, List[Dict[str, str]]]:
    buckets: Dict[str, List[Dict[str, str]]] = {}
    for term in terms:
        key = key_getter(term)
        if not key:
            continue
        buckets.setdefault(key, []).append(
            {
                "id": term["id"],
                "value": value_getter(term),
                "category": term.get("categoryId", ""),
            }
        )
    return {k: sorted(v, key=lambda item: item["id"]) for k, v in buckets.items() if len(v) > 1}


def analyze_terms(
    terms: List[Dict],
    categories: List[Dict],
    sources_payload: Dict | None,
    source_load_errors: List[Dict[str, str]],
) -> Dict:
    duplicate_ja = detect_duplicates(
        terms,
        lambda term: normalize_ja(term.get("ja")),
        lambda term: term.get("ja", ""),
    )
    duplicate_pt = detect_duplicates(
        terms,
        lambda term: normalize_pt((term.get("translations") or {}).get("pt")),
        lambda term: (term.get("translations") or {}).get("pt", ""),
    )

    type_mismatches = []
    missing_search = []
    empty_search = []
    auto_fix_preview = []
    structural_errors = []
    duplicate_ids: List[str] = []
    unknown_categories: List[Dict[str, str]] = []
    sources_errors: List[Dict[str, str]] = list(source_load_errors)
    sources_warnings: List[Dict[str, str]] = []
    term_source_errors: List[Dict[str, str]] = []
    referenced_sources: set[str] = set()

    sources_index: Dict[str, Dict] = {}
    if sources_payload is not None:
        sources_list = sources_payload.get("sources")
        if not isinstance(sources_list, list):
            sources_errors.append(
                {"id": "<payload>", "field": "sources", "detail": "sources must be a list"}
            )
        else:
            seen_source_ids: set[str] = set()
            for source in sources_list:
                if not isinstance(source, dict):
                    sources_errors.append(
                        {"id": "<payload>", "field": "source", "detail": "Each source must be an object"}
                    )
                    continue
                sid = source.get("id")
                if not isinstance(sid, str) or not sid:
                    sources_errors.append({"id": "<missing>", "field": "id", "detail": "Source ID missing"})
                    continue
                if not SOURCE_ID_RE.fullmatch(sid):
                    sources_errors.append(
                        {"id": sid, "field": "id", "detail": "Source ID must match S####"}
                    )
                    continue
                if sid in seen_source_ids:
                    sources_errors.append({"id": sid, "field": "id", "detail": "Duplicate source ID"})
                    continue
                seen_source_ids.add(sid)
                title = source.get("title")
                stype = source.get("type")
                if not isinstance(title, str) or not title.strip():
                    sources_errors.append({"id": sid, "field": "title", "detail": "Title is required"})
                if not isinstance(stype, str) or not stype.strip():
                    sources_errors.append({"id": sid, "field": "type", "detail": "Type is required"})
                url = source.get("url")
                if url:
                    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                        sources_warnings.append(
                            {"id": sid, "field": "url", "detail": "URL should start with http/https"}
                        )
                accessed_at = source.get("accessed_at")
                if accessed_at:
                    if not isinstance(accessed_at, str) or not ISO_DATE_RE.fullmatch(accessed_at):
                        sources_warnings.append(
                            {
                                "id": sid,
                                "field": "accessed_at",
                                "detail": "Use YYYY-MM-DD format",
                            }
                        )
                sources_index[sid] = source

    seen_ids: set[str] = set()
    valid_categories = {item.get("id") for item in categories if item.get("id")}

    for term in sorted(terms, key=lambda t: t.get("id", "")):
        term_id = term.get("id")
        if not term_id:
            structural_errors.append({"id": "<missing>", "field": "id", "detail": "ID is required"})
            continue
        if term_id in seen_ids:
            duplicate_ids.append(term_id)
        seen_ids.add(term_id)

        ja_original = term.get("ja", "")
        ja_text = normalize_common(ja_original)
        translations = term.get("translations") or {}
        pt_original = translations.get("pt", "")
        pt_text = normalize_common(pt_original)

        if not ja_original:
            structural_errors.append({"id": term_id, "field": "ja", "detail": "Japanese text missing"})

        if not translations or not pt_original:
            structural_errors.append({"id": term_id, "field": "translations.pt", "detail": "Portuguese text missing"})

        category_id = term.get("categoryId")
        if not category_id:
            structural_errors.append({"id": term_id, "field": "categoryId", "detail": "Category missing"})
        elif valid_categories and category_id not in valid_categories:
            unknown_categories.append({"id": term_id, "category": category_id})

        expected_type = infer_type(ja_text, pt_text)
        reason = type_reason(ja_text, pt_text)
        current_type = term.get("type", "term")
        if expected_type != current_type:
            type_mismatches.append(
                {
                    "id": term_id,
                    "current": current_type,
                    "expected": expected_type,
                    "ja": ja_original,
                    "reason": reason,
                }
            )

        desired_search = build_search_payload(term)
        existing = term.get("search") or {}
        needs_search = existing.get("ja") != desired_search["ja"] or existing.get("pt") != desired_search["pt"]

        if needs_search:
            missing_search.append({"id": term_id, "ja": ja_original})
            auto_fix_preview.append(
                {
                    "id": term_id,
                    "add_search": "YES" if not term.get("search") else "NO",
                    "update_type": "YES" if expected_type != current_type else "NO",
                }
            )

        if not desired_search["ja"] or not desired_search["pt"]:
            empty_search.append({"id": term_id, "ja": ja_original})

        sources_field = term.get("sources")
        if sources_field is None:
            term_source_errors.append({"id": term_id, "detail": "sources field missing"})
        elif not isinstance(sources_field, list):
            term_source_errors.append({"id": term_id, "detail": "sources must be a list"})
        else:
            for entry in sources_field:
                if not isinstance(entry, str) or not entry:
                    term_source_errors.append(
                        {"id": term_id, "detail": "Source references must be non-empty strings"}
                    )
                    continue
                if sources_index and entry not in sources_index:
                    term_source_errors.append(
                        {"id": term_id, "detail": f"Unknown source ID {entry}"}
                    )
                if entry in sources_index:
                    referenced_sources.add(entry)

    unused_sources = sorted(sid for sid in sources_index if sid not in referenced_sources)

    blocking_issues = []
    if structural_errors:
        blocking_issues.append(f"{len(structural_errors)} structural issues detected")
    if duplicate_ids:
        blocking_issues.append(f"Duplicate term IDs: {', '.join(sorted(duplicate_ids))}")
    if unknown_categories:
        blocking_issues.append(f"{len(unknown_categories)} terms reference unknown categories")
    if type_mismatches:
        blocking_issues.append(f"{len(type_mismatches)} type mismatches (see Section 3)")
    if missing_search:
        blocking_issues.append(f"{len(missing_search)} terms missing search field (see Section 4)")
    if sources_errors:
        blocking_issues.append(f"{len(sources_errors)} source ledger errors (see Section 5)")
    if term_source_errors:
        blocking_issues.append(f"{len(term_source_errors)} term source issues (see Section 5)")

    status = "PASS"
    if blocking_issues:
        status = "FAIL"
    elif duplicate_ja or duplicate_pt or empty_search or sources_warnings or unused_sources:
        status = "WARN"

    return {
        "terms_total": len(terms),
        "categories_total": len(categories),
        "duplicate_ja": duplicate_ja,
        "duplicate_pt": duplicate_pt,
        "type_mismatches": type_mismatches,
        "missing_search": missing_search,
        "empty_search": empty_search,
        "auto_fix_preview": auto_fix_preview,
        "structural_errors": structural_errors,
        "duplicate_ids": duplicate_ids,
        "unknown_categories": unknown_categories,
        "sources_errors": sources_errors,
        "sources_warnings": sources_warnings,
        "term_source_errors": term_source_errors,
        "unused_sources": unused_sources,
        "blocking_issues": blocking_issues,
        "status": status,
    }


def apply_fixes(terms: List[Dict]) -> FixStats:
    stats = FixStats()
    modified_ids: set[str] = set()
    for term in terms:
        term_id = term.get("id", "")
        ja_text = normalize_common(term.get("ja"))
        translations = term.get("translations") or {}
        pt_text = normalize_common(translations.get("pt"))
        expected_type = infer_type(ja_text, pt_text)
        current_type = term.get("type", "term")
        if expected_type != current_type:
            term["type"] = expected_type
            stats.type_updates += 1
            if term_id:
                modified_ids.add(term_id)

        desired_search = build_search_payload(term)
        existing = term.get("search") or {}
        if existing.get("ja") != desired_search["ja"] or existing.get("pt") != desired_search["pt"]:
            term["search"] = desired_search
            stats.search_updates += 1
            if term_id:
                modified_ids.add(term_id)

        if "sources" not in term:
            term["sources"] = []
            stats.sources_added += 1
            if term_id:
                modified_ids.add(term_id)

    stats.terms_modified = len(modified_ids)
    stats.json_modified = bool(modified_ids)
    return stats


def default_report_path(mode: str) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    return REPORT_ROOT / f"audit_{mode}_{timestamp}.md"


def render_duplicates(duplicates: Dict[str, List[Dict[str, str]]]) -> str:
    if not duplicates:
        return "None"
    lines = []
    for normalized in sorted(duplicates):
        lines.append(f"- {normalized}:")
        for entry in duplicates[normalized]:
            lines.append(f"  - {entry['id']} | {entry['value']} | {entry['category']}")
    return "\n".join(lines)


def render_type_mismatches(mismatches: List[Dict[str, str]]) -> str:
    if not mismatches:
        return "None"
    lines = []
    for item in mismatches:
        lines.extend(
            [
                f"- {item['id']}",
                f"  - Current: {item['current']}",
                f"  - Expected: {item['expected']}",
                f"  - JA: {item['ja']}",
                f"  - Reason: {item['reason']}",
            ]
        )
    return "\n".join(lines)


def render_simple_list(items: List[Dict[str, str]]) -> str:
    if not items:
        return "None"
    return "\n".join(f"- {item['id']} | {item['ja']}" for item in items)


def render_auto_fix_preview(entries: List[Dict[str, str]]) -> str:
    if not entries:
        return "None"
    lines = []
    for entry in entries:
        lines.extend(
            [
                f"- {entry['id']}",
                f"  - Add search: {entry['add_search']}",
                f"  - Update type: {entry['update_type']}",
            ]
        )
    return "\n".join(lines)


def render_source_issue_list(items: List[Dict[str, str]]) -> str:
    if not items:
        return "None"
    lines = []
    for item in items:
        field = item.get("field", "-")
        detail = item.get("detail", "")
        lines.append(f"- {item.get('id', '<unknown>')} | {field} | {detail}")
    return "\n".join(lines)


def render_term_source_issues(items: List[Dict[str, str]]) -> str:
    if not items:
        return "None"
    return "\n".join(f"- {item['id']} | {item['detail']}" for item in items)


def render_unused_sources(ids: List[str]) -> str:
    if not ids:
        return "None"
    return "\n".join(f"- {sid}" for sid in ids)


def render_fix_section(stats: FixStats, duplicate_count: int) -> str:
    lines = [
        f"- Terms updated: {stats.terms_modified}",
        f"- Types updated: {stats.type_updates}",
        f"- Search fields generated: {stats.search_updates}",
        f"- Sources initialized: {stats.sources_added}",
        f"- Duplicates flagged (not auto-removed): {duplicate_count}",
        "\nJSON modified:",
        f"- {'YES' if stats.json_modified else 'NO'}",
    ]
    return "\n".join(lines)


def recommended_action(status: str) -> str:
    if status == "PASS":
        return "Safe to merge"
    if status == "WARN":
        return "Merge after review"
    return "Do not merge"


def render_report(mode: str, analysis: Dict, fix_stats: FixStats, include_preview: bool) -> str:
    summary_lines = [
        f"- Terms total: {analysis['terms_total']}",
        f"- Categories total: {analysis['categories_total']}",
        f"- Duplicate JA: {len(analysis['duplicate_ja'])}",
        f"- Duplicate PT: {len(analysis['duplicate_pt'])}",
        f"- Type mismatch: {len(analysis['type_mismatches'])}",
        f"- Missing search field: {len(analysis['missing_search'])}",
        f"- Source ledger errors: {len(analysis['sources_errors'])}",
        f"- Source ledger warnings: {len(analysis['sources_warnings'])}",
        f"- Unreferenced sources: {len(analysis['unused_sources'])}",
        f"- Auto-fix required: {'YES' if analysis['status'] == 'FAIL' else 'NO'}",
        "",
        "Overall Status:",
        f"- {analysis['status']}",
        "  - PASS (no blocking issues)",
        "  - WARN (non-breaking improvements)",
        "  - FAIL (blocking issues present)",
    ]

    blocking = "\n".join(f"- {item}" for item in analysis["blocking_issues"]) or "None"

    sections = [
        "# Audit Report Specification",
        "Project: jp-pt-school-terms",
        "Scope: Issue #2 – Data Quality Automation / Issue #3 – Sources Ledger MVP",
        f"Generated by: scripts/audit_terms.py --{mode}",
        "\n---\n",
        "# 1. Summary\n" + "\n".join(summary_lines),
        "\n---\n",
        "# 2. Duplicate Detection",
        "\n## 2.1 JA Duplicates\n" + render_duplicates(analysis["duplicate_ja"]),
        "\n---\n",
        "## 2.2 PT Duplicates\n" + render_duplicates(analysis["duplicate_pt"]),
        "\n---\n",
        "# 3. Type Reclassification",
        "\n## 3.1 Type Mismatch\n" + render_type_mismatches(analysis["type_mismatches"]),
        "\n---\n",
        "# 4. Search Field Audit",
        "\n## 4.1 Missing Search\n" + render_simple_list(analysis["missing_search"]),
        "\n\n## 4.2 Empty Search Arrays\n" + render_simple_list(analysis["empty_search"]),
        "\n---\n",
        "# 5. Sources Ledger Audit",
        "\n## 5.1 Ledger Errors (FAIL)\n" + render_source_issue_list(analysis["sources_errors"]),
        "\n---\n",
        "## 5.2 Ledger Warnings (WARN)\n" + render_source_issue_list(analysis["sources_warnings"]),
        "\n---\n",
        "## 5.3 Term Reference Issues\n" + render_term_source_issues(analysis["term_source_errors"]),
        "\n---\n",
        "## 5.4 Unreferenced Sources\n" + render_unused_sources(analysis["unused_sources"]),
        "\n---\n",
    ]

    if include_preview:
        sections.append("# 6. Auto-Fix Preview\n" + render_auto_fix_preview(analysis["auto_fix_preview"]))
        sections.append("\n---\n")
        sections.append(
            "# 7. Fix Execution Report (Only when --fix used)\nNot executed (ran with --check).\n\n- Terms updated: None\n- Types updated: None\n- Search fields generated: None\n- Sources initialized: None\n- Duplicates flagged (not auto-removed): None\n\nJSON modified:\n- NO"
        )
    else:
        sections.append("# 6. Auto-Fix Preview\nNone")
        sections.append("\n---\n")
        sections.append(
            "# 7. Fix Execution Report (Only when --fix used)\n" + render_fix_section(
                fix_stats, len(analysis["duplicate_ja"]) + len(analysis["duplicate_pt"])
            )
        )

    sections.append("\n---\n")
    sections.append("# 8. Blocking Issues\n" + blocking)

    sections.extend(
        [
            "\n---\n",
            "# 9. Recommended Action\n- " + recommended_action(analysis["status"]),
            "\n---\n",
            "# Output Rules\nSee work_md/AUDIT_REPORT_SPEC.md",
            "\n---\n",
            "# End of Report",
        ]
    )

    return "\n".join(sections)


def ensure_report_path(arg_path: str | None, mode: str) -> Path:
    if arg_path:
        path = Path(arg_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    return default_report_path(mode)


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Audit terms.json data quality")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Report findings only")
    group.add_argument("--fix", action="store_true", help="Apply fixes (type/search)")
    parser.add_argument("--report-out", dest="report_out", help="Optional path to save the report")
    args = parser.parse_args(argv)

    payload = load_terms()
    terms = payload.get("terms", [])
    categories = payload.get("categories", [])

    sources_payload: Dict | None = None
    source_load_errors: List[Dict[str, str]] = []
    try:
        sources_payload = load_sources()
    except FileNotFoundError:
        source_load_errors.append(
            {"id": "sources.json", "field": "file", "detail": "sources.json missing"}
        )
    except json.JSONDecodeError as exc:
        source_load_errors.append(
            {"id": "sources.json", "field": "file", "detail": f"Invalid JSON: {exc}"}
        )

    analysis_before = analyze_terms(terms, categories, sources_payload, source_load_errors)
    fix_stats = FixStats()

    mode = "fix" if args.fix else "check"

    if args.fix:
        fix_stats = apply_fixes(terms)
        if fix_stats.json_modified:
            write_terms(payload)
        analysis_after = analyze_terms(terms, categories, sources_payload, source_load_errors)
    else:
        analysis_after = analysis_before

    report_path = ensure_report_path(args.report_out, mode)
    report_content = render_report(mode, analysis_after, fix_stats, include_preview=not args.fix)
    report_path.write_text(report_content, encoding="utf-8")

    print(report_content)
    print(f"\nReport saved to {report_path}")

    return 0 if analysis_after["status"] != "FAIL" else 1


if __name__ == "__main__":
    sys.exit(main())
