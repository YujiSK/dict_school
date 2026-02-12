#!/usr/bin/env python3
"""Audit and maintenance utilities for terms.json."""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
TERMS_PATH = REPO_ROOT / "terms.json"
REPORT_ROOT = REPO_ROOT / "work_md" / "audit_reports"

JA_SENTENCE_TOKENS = "。？！!?"
PHRASE_HINTS = {" ", "　", "・", "／", "+", "-", "〜", "…", "→"}
PHRASE_KEYWORDS = ["ください", "お願いします", "します", "しません", "しますか", "ませんか"]


@dataclass
class FixStats:
    type_updates: int = 0
    search_updates: int = 0
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
    base = normalize_pt(value)
    if not base:
        return []
    return [token for token in re.split(r"[^a-z0-9]+", base) if token]


def infer_type(text: str) -> str:
    if not text:
        return "term"
    if any(token in text for token in JA_SENTENCE_TOKENS) or len(text) >= 25:
        return "sentence"
    if any(keyword in text for keyword in PHRASE_KEYWORDS):
        return "phrase"
    if any(hint in text for hint in PHRASE_HINTS):
        return "phrase"
    if len(text) >= 12:
        return "phrase"
    return "term"


def type_reason(text: str) -> str:
    if not text:
        return "Empty text defaulted to term"
    if any(token in text for token in JA_SENTENCE_TOKENS):
        return "Contains sentence-ending punctuation"
    if len(text) >= 25:
        return "Length >= 25 characters"
    if any(keyword in text for keyword in PHRASE_KEYWORDS):
        return "Contains request/intent keyword"
    if any(hint in text for hint in PHRASE_HINTS):
        return "Contains phrase delimiter character"
    if len(text) >= 12:
        return "Length >= 12 characters"
    return "Length < 12 and no delimiters"


def unique(seq: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for item in seq:
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def build_search_payload(term: Dict) -> Dict[str, List[str]]:
    ja_candidates = [
        normalize_common(term.get("ja")),
        normalize_ja(term.get("ja")),
        normalize_common(term.get("jaEasy")),
    ]
    translations = term.get("translations") or {}
    pt_raw = translations.get("pt")
    pt_candidates = [normalize_common(pt_raw), normalize_pt(pt_raw)] + tokenize_pt(pt_raw)
    return {
        "ja": unique([c for c in ja_candidates if c]),
        "pt": unique([c for c in pt_candidates if c]),
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


def analyze_terms(terms: List[Dict], categories: List[Dict]) -> Dict:
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

    for term in sorted(terms, key=lambda t: t["id"]):
        ja_text = normalize_common(term.get("ja"))
        expected_type = infer_type(ja_text)
        reason = type_reason(ja_text)
        current_type = term.get("type", "term")
        if expected_type != current_type:
            type_mismatches.append(
                {
                    "id": term["id"],
                    "current": current_type,
                    "expected": expected_type,
                    "ja": term.get("ja", ""),
                    "reason": reason,
                }
            )

        desired_search = build_search_payload(term)
        existing = term.get("search") or {}
        needs_search = existing.get("ja") != desired_search["ja"] or existing.get("pt") != desired_search["pt"]

        if needs_search:
            missing_search.append({"id": term["id"], "ja": term.get("ja", "")})
            add_search = not term.get("search")
            normalize_flag = ja_text != term.get("ja", "")
            auto_fix_preview.append(
                {
                    "id": term["id"],
                    "add_search": "YES" if add_search else "NO",
                    "update_type": "YES" if expected_type != current_type else "NO",
                    "normalize": "YES" if normalize_flag else "NO",
                }
            )
        else:
            if not desired_search["ja"] or not desired_search["pt"]:
                empty_search.append({"id": term["id"], "ja": term.get("ja", "")})

    blocking_issues = []
    if type_mismatches:
        blocking_issues.append(f"{len(type_mismatches)} type mismatches (see Section 3)")
    if missing_search:
        blocking_issues.append(f"{len(missing_search)} terms missing search field (see Section 4)")

    status = "PASS"
    if blocking_issues:
        status = "FAIL"
    elif duplicate_ja or duplicate_pt or empty_search:
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
        "blocking_issues": blocking_issues,
        "status": status,
    }


def apply_fixes(terms: List[Dict]) -> FixStats:
    stats = FixStats()
    modified_ids: set[str] = set()
    for term in terms:
        ja_text = normalize_common(term.get("ja"))
        expected_type = infer_type(ja_text)
        current_type = term.get("type", "term")
        if expected_type != current_type:
            term["type"] = expected_type
            stats.type_updates += 1
            modified_ids.add(term["id"])

        desired_search = build_search_payload(term)
        existing = term.get("search") or {}
        if existing.get("ja") != desired_search["ja"] or existing.get("pt") != desired_search["pt"]:
            term["search"] = desired_search
            stats.search_updates += 1
            modified_ids.add(term["id"])

    stats.terms_modified = len(modified_ids)
    stats.json_modified = bool(modified_ids)
    return stats


def default_report_path(mode: str) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
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
                f"  - Normalize suggested: {entry['normalize']}",
            ]
        )
    return "\n".join(lines)


def render_fix_section(stats: FixStats, duplicate_count: int) -> str:
    lines = [
        f"- Terms updated: {stats.terms_modified}",
        f"- Types updated: {stats.type_updates}",
        f"- Search fields generated: {stats.search_updates}",
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
        "Scope: Issue #2 – Data Quality Automation",
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
    ]

    if include_preview:
        sections.append("# 5. Auto-Fix Preview\n" + render_auto_fix_preview(analysis["auto_fix_preview"]))
        sections.append("\n---\n")
        sections.append(
            "# 6. Fix Execution Report (Only when --fix used)\nNot executed (ran with --check).\n\n- Terms updated: None\n- Types updated: None\n- Search fields generated: None\n- Duplicates flagged (not auto-removed): None\n\nJSON modified:\n- NO"
        )
    else:
        sections.append("# 5. Auto-Fix Preview\nNone")
        sections.append("\n---\n")
        sections.append(
            "# 6. Fix Execution Report (Only when --fix used)\n" + render_fix_section(
                fix_stats, len(analysis["duplicate_ja"]) + len(analysis["duplicate_pt"])
            )
        )

    sections.extend(
        [
            "\n---\n",
            "# 7. Blocking Issues\n" + blocking,
            "\n---\n",
            "# 8. Recommended Action\n- " + recommended_action(analysis["status"]),
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
    parser = argparse.ArgumentParser(description="Audit terms.json data quality")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Report findings only")
    group.add_argument("--fix", action="store_true", help="Apply fixes (type/search)")
    parser.add_argument("--report-out", dest="report_out", help="Optional path to save the report")
    args = parser.parse_args(argv)

    payload = load_terms()
    terms = payload.get("terms", [])
    categories = payload.get("categories", [])

    analysis_before = analyze_terms(terms, categories)
    fix_stats = FixStats()

    mode = "fix" if args.fix else "check"

    if args.fix:
        fix_stats = apply_fixes(terms)
        if fix_stats.json_modified:
            write_terms(payload)
        analysis_after = analyze_terms(terms, categories)
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
