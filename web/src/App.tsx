import { useEffect, useMemo, useState } from "react";

type Category = { id: string; name: { ja: string; pt?: string; en?: string } };
type SourceRef = { sourceId: string; page: number | null; note?: string };

type Term = {
  id: string;
  type: "phrase" | "term" | "sentence";
  categoryId: string;
  ja: string;
  jaEasy?: string;
  translations: { pt?: string; en?: string };
  sourceRefs?: SourceRef[];
  search?: { ja?: string[]; pt?: string[]; en?: string[] };
};

type TermsJson = {
  meta: Record<string, unknown>;
  categories: Category[];
  terms: Term[];
};

export default function App() {
  const [data, setData] = useState<TermsJson | null>(null);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState<string>("ALL");
  const [teacherId, setTeacherId] = useState<string | null>(null);

  useEffect(() => {
    fetch("/terms.json")
      .then((r) => r.json())
      .then(setData)
      .catch((e) => {
        console.error(e);
        setData(null);
      });
  }, []);

  const categories = useMemo(() => data?.categories ?? [], [data]);
  const terms = useMemo(() => data?.terms ?? [], [data]);

  const selectedTerm = useMemo(
    () => (teacherId ? terms.find((t) => t.id === teacherId) ?? null : null),
    [teacherId, terms]
  );

  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase();
    return terms
      .filter((t) => (cat === "ALL" ? true : t.categoryId === cat))
      .filter((t) => {
        if (!query) return true;

        const ja = t.ja?.toLowerCase() ?? "";
        const pt = (t.translations?.pt ?? "").toLowerCase();
        const jaSearch = (t.search?.ja ?? []).join(" ").toLowerCase();
        const ptSearch = (t.search?.pt ?? []).join(" ").toLowerCase();

        return (
          ja.includes(query) ||
          pt.includes(query) ||
          jaSearch.includes(query) ||
          ptSearch.includes(query)
        );
      })
      .slice(0, 10);
  }, [terms, q, cat]);

  if (!data) {
    return (
      <div style={{ padding: 16, fontFamily: "system-ui" }}>
        <h1>Dict School (MVP)</h1>
        <p>terms.json を読み込み中…（/public/terms.json を確認）</p>
      </div>
    );
  }

  return (
    <div style={{ padding: 16, fontFamily: "system-ui", maxWidth: 900, margin: "0 auto" }}>
      <h1 style={{ marginBottom: 12 }}>学校用語辞書（JP ⇔ PT）MVP</h1>

      {/* Controls */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="検索（日本語 / português）"
          style={{ padding: 10, minWidth: 260, flex: "1 1 260px" }}
        />

        <select value={cat} onChange={(e) => setCat(e.target.value)} style={{ padding: 10 }}>
          <option value="ALL">全カテゴリ</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name?.ja ?? c.id}
            </option>
          ))}
        </select>
      </div>

      {/* List */}
      <div style={{ display: "grid", gap: 10 }}>
        {filtered.map((t) => (
          <div
            key={t.id}
            style={{
              border: "1px solid #ddd",
              borderRadius: 12,
              padding: 12,
              display: "grid",
              gap: 6,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <div style={{ fontSize: 12, opacity: 0.7 }}>
                {t.id} / {t.type} / {t.categoryId}
              </div>
              <button
                onClick={() => setTeacherId(t.id)}
                style={{ padding: "6px 10px", borderRadius: 10, border: "1px solid #ccc" }}
              >
                先生に見せる
              </button>
            </div>

            <div style={{ fontSize: 22, fontWeight: 700 }}>{t.ja}</div>
            <div style={{ fontSize: 18 }}>{t.translations?.pt ?? ""}</div>
          </div>
        ))}

        {filtered.length === 0 && <div style={{ opacity: 0.7 }}>該当なし</div>}
      </div>

      {/* Teacher mode modal */}
      {selectedTerm && (
        <div
          onClick={() => setTeacherId(null)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "grid",
            placeItems: "center",
            padding: 16,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "white",
              width: "min(900px, 100%)",
              borderRadius: 16,
              padding: 18,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <div style={{ fontSize: 12, opacity: 0.7 }}>{selectedTerm.id}</div>
              <button
                onClick={() => setTeacherId(null)}
                style={{ padding: "6px 10px", borderRadius: 10, border: "1px solid #ccc" }}
              >
                閉じる
              </button>
            </div>

            <div style={{ fontSize: 44, fontWeight: 800, marginTop: 10 }}>{selectedTerm.ja}</div>
            <div style={{ fontSize: 30, marginTop: 10 }}>{selectedTerm.translations?.pt ?? ""}</div>

            <div style={{ marginTop: 14, fontSize: 12, opacity: 0.7 }}>
              ※この画面を先生に見せてください（最小MVP）
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
