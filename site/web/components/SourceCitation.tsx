import type { Citation } from "@/lib/api";

export default function SourceCitation({ citations }: { citations: Citation[] }) {
  if (!citations?.length) return null;
  return (
    <div className="mt-3 text-xs opacity-70 leading-relaxed">
      {citations.map((c, i) => (
        <div key={i}>
          Sumber: <code>{c.table}</code>
          {c.basis ? ` — ${c.basis}` : ""}
        </div>
      ))}
    </div>
  );
}
