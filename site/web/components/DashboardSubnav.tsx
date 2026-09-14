"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/papan-pemuka/ringkasan", label: "Ringkasan Perbandingan" },
  { href: "/papan-pemuka/perkembangan", label: "Perkembangan Komponen" },
  { href: "/papan-pemuka/kementerian", label: "Mengikut Kementerian" },
];

export default function DashboardSubnav() {
  const pathname = usePathname();
  return (
    <div className="flex gap-2 mb-6 border-b" style={{ borderColor: "var(--line)" }}>
      {TABS.map((tab) => {
        const active = pathname?.startsWith(tab.href);
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className="px-3 py-2 text-sm -mb-px border-b-2 transition-colors"
            style={{
              borderColor: active ? "var(--accent)" : "transparent",
              opacity: active ? 1 : 0.65,
              fontWeight: active ? 600 : 400,
            }}
          >
            {tab.label}
          </Link>
        );
      })}
    </div>
  );
}
