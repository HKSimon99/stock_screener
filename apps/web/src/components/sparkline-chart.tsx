"use client";

import { useEffect, useState } from "react";
import { getBaseUrl } from "@/lib/api";

interface SparklineChartProps {
  ticker: string;
  market: "US" | "KR";
  /** Width in px (default 80) */
  width?: number;
  /** Height in px (default 28) */
  height?: number;
  className?: string;
}

function buildSparklinePath(closes: number[], w: number, h: number): string {
  if (closes.length < 2) return "";
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;
  const pad = 2;

  const points = closes.map((v, i) => {
    const x = pad + (i / (closes.length - 1)) * (w - pad * 2);
    const y = pad + (1 - (v - min) / range) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  return `M ${points.join(" L ")}`;
}

export function SparklineChart({
  ticker,
  market,
  width = 80,
  height = 28,
  className = "",
}: SparklineChartProps) {
  const [closes, setCloses] = useState<number[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    const base = getBaseUrl().replace("/api/v1", "");
    fetch(`${base}/api/v1/instruments/${market}/${ticker}/sparkline?points=16`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (!cancelled && data?.closes?.length >= 2) {
          setCloses(data.closes);
        }
      })
      .catch(() => {/* silent fail — sparkline is decorative */});
    return () => { cancelled = true; };
  }, [ticker, market]);

  if (!closes) {
    // Loading skeleton
    return (
      <div
        className={`rounded animate-pulse bg-white/6 ${className}`}
        style={{ width, height }}
      />
    );
  }

  const path = buildSparklinePath(closes, width, height);
  const first = closes[0];
  const last = closes[closes.length - 1];
  const isUp = last >= first;
  const color = isUp
    ? "oklch(0.72 0.18 145)"   // emerald
    : "oklch(0.62 0.22 25)";   // crimson

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      aria-hidden="true"
    >
      <path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.85"
      />
    </svg>
  );
}
