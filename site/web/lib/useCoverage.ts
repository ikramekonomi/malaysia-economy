"use client";

import { useEffect, useState } from "react";
import { Coverage, DEFAULT_COVERAGE, fetchCoverage } from "@/lib/api";

/** The warehouse's year coverage, read from the API so a new year (or a newly audited one)
 *  appears on the site without a code change. Falls back to DEFAULT_COVERAGE until loaded. */
export function useCoverage(): Coverage {
  const [cov, setCov] = useState<Coverage>(DEFAULT_COVERAGE);
  useEffect(() => {
    let stale = false;
    fetchCoverage()
      .then((c) => {
        if (!stale) setCov(c);
      })
      .catch(() => {});
    return () => {
      stale = true;
    };
  }, []);
  return cov;
}

export function yearRange(from: number, to: number): number[] {
  return Array.from({ length: to - from + 1 }, (_, i) => from + i);
}
