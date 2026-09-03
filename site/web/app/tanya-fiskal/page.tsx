"use client";

import { useState } from "react";
import { Citation, askChat } from "@/lib/api";
import SourceCitation from "@/components/SourceCitation";

type Turn = { role: "user" | "assistant"; text: string; citations?: Citation[] };

const EXAMPLES = [
  "Berapakah OPEX pada 2024?",
  "Apakah perbelanjaan Kementerian Pertanian dari 2010 hingga 2015?",
  "Berapakah jumlah hasil kerajaan pada 2023?",
];

export default function TanyaFiskalPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(question: string) {
    if (!question.trim() || loading) return;
    setError(null);
    setInput("");
    setTurns((t) => [...t, { role: "user", text: question }]);
    setLoading(true);
    try {
      const res = await askChat(question);
      setTurns((t) => [...t, { role: "assistant", text: res.answer, citations: res.citations }]);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-5 py-10">
      <h1 className="text-2xl font-semibold mb-1">Tanya Fiskal</h1>
      <p className="text-sm opacity-70 mb-6">
        Tanya soalan tentang kewangan awam persekutuan. Setiap jawapan datang daripada
        data teraudit/rasmi sahaja, dengan sumber dinyatakan — bukan anggaran model bahasa.
      </p>

      {turns.length === 0 && (
        <div className="flex flex-wrap gap-2 mb-6">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              onClick={() => send(ex)}
              className="text-xs px-3 py-1.5 rounded-full border hover:opacity-70"
              style={{ borderColor: "var(--line)" }}
            >
              {ex}
            </button>
          ))}
        </div>
      )}

      <div className="space-y-4 mb-6">
        {turns.map((t, i) => (
          <div
            key={i}
            className={`rounded border p-4 ${t.role === "user" ? "" : ""}`}
            style={{
              borderColor: "var(--line)",
              background: t.role === "user" ? "var(--accent-soft)" : "var(--panel)",
            }}
          >
            <div className="text-xs opacity-60 mb-1">{t.role === "user" ? "Anda" : "Tanya Fiskal"}</div>
            <div className="whitespace-pre-wrap text-sm">{t.text}</div>
            {t.citations && <SourceCitation citations={t.citations} />}
          </div>
        ))}
        {loading && <div className="text-sm opacity-60">Mencari jawapan…</div>}
        {error && <div className="text-sm text-red-600">{error}</div>}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex gap-2"
      >
        <input
          className="flex-1 border rounded px-3 py-2 text-sm"
          style={{ borderColor: "var(--line)" }}
          placeholder="Taip soalan anda…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 rounded text-sm font-medium text-white disabled:opacity-50"
          style={{ background: "var(--accent)" }}
        >
          Hantar
        </button>
      </form>
    </div>
  );
}
