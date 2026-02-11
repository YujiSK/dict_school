# v0.2 Schema Design (Adopted Plan A: Include 'en')

## 1. Overview
The data schema will be refactored to support future extensibility, including multilingual support (en/es/vi in future), "Easy Japanese" (jaEasy), term types (phrase/term/sentence), and precise source referencing (page numbers).

**Key Decision:** Adopt Plan A (Include `en` field from the start) to stabilize the data structure.

---

## 2. `sources.json` (v0.2)

```json
{
  "meta": {
    "name": "jp-pt-school-terms-sources",
    "version": "0.2.0",
    "updatedAt": "2026-02-12",
    "policy": {
      "copyingRule": "PDFの表・例文・解説文は転載しない。対訳語は参照して独自データとして再編集する。",
      "licenseRule": "利用条件URLを必ず保持。不明は status=needs_review にし、terms側では採用保留できる状態にする。"
    }
  },
  "sources": [
    {
      "id": "S002",
      "title": "がっこうのことば（第2版）ポルトガル語版",
      "publisher": "西尾市教育委員会",
      "publisherType": "local_gov",
      "region": "Aichi / Nishio",
      "primaryDomain": "city.nishio.aichi.jp",
      "urls": {
        "page": "https://tabunkakibou.com/resource/",
        "pdf": "https://www.city.nishio.aichi.jp/_res/projects/default_project/_page_/001/002/407/1006poru.pdf"
      },
      "publishedAt": "2021-04",
      "languages": ["ja", "pt"],
      "scopeTags": ["school_terms", "school_life", "letters", "common_phrases"],
      "license": {
        "type": "unclear",
        "licenseUrl": "https://tabunkakibou.com/resource/",
        "evidence": "ページに「ダウンロードして使えます」とあるが、転載・改変・再配布許諾の明文化は未確認。"
      },
      "status": "needs_review",
      "notes": "初期100語の“語彙選定の現場性”として非常に有用。辞書データは独自編集で作る前提。"
    }
    // ... migrate other sources similarly
  ]
}
```

---

## 3. `terms.json` (v0.2)

```json
{
  "meta": {
    "name": "jp-pt-school-terms",
    "version": "0.2.0",
    "updatedAt": "2026-02-12",
    "defaultLanguages": ["ja", "pt", "en"],
    "uiModes": ["parent", "teacher"]
  },
  "categories": [
    { "id": "C01", "name": { "ja": "提出・同意・連絡（定型文）", "pt": "", "en": "" } },
    { "id": "C02", "name": { "ja": "行事・面談・検診・訓練（学校運営）", "pt": "", "en": "" } },
    { "id": "C03", "name": { "ja": "場所・設備（校内）", "pt": "", "en": "" } },
    { "id": "C04", "name": { "ja": "学校種・基本（学年など）", "pt": "", "en": "" } }
  ],
  "terms": [
    {
      "id": "T0001",
      "type": "phrase", // phrase | term | sentence
      "categoryId": "C01",

      "ja": "提出してください",
      "jaEasy": "", // To be filled later

      "translations": {
        "pt": "Favor apresentar",
        "en": "" // Included as per Plan A
      },

      "examples": {}, // Initially empty or default structure

      "sourceRefs": [
        { "sourceId": "S002", "page": null, "note": "" } // Migrated from source_ids
      ],

      "search": {
        "ja": ["提出", "提出してください"], // Generated from ja
        "pt": ["apresentar", "entregar"], // Generated from pt translations
        "en": []
      },

      "status": "draft",
      "confidence": 0.8,
      "notes": ""
    }
    // ... migrate all terms similarly
  ]
}
```

## 4. Migration Rules applied to v0.1 data
1.  **categories**: Kept IDs `C01`-`C04`. Names moved to `name.ja`.
2.  **terms**:
    *   `category_id` -> `categoryId`
    *   `source_ids` -> `sourceRefs` (page: null)
    *   `pt` -> `translations.pt`
    *   `ja` -> `ja`
    *   `type`: Inferred.
        *   Ends with "ください/ます/ません" -> `phrase`
        *   Otherwise -> `term` (default)
    *   `search.ja`: Tokenized from `ja`.
    *   `search.pt`: Tokenized from `pt`.
