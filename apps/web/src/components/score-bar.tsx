interface ScoreBarProps {
  label: string;
  score: number;
  color?: string;
}

export function ScoreBar({ label, score, color }: ScoreBarProps) {
  const clampedScore = Math.max(0, Math.min(100, score));

  const barColor =
    color ??
    (clampedScore >= 70
      ? "bg-emerald-500"
      : clampedScore >= 50
        ? "bg-amber-500"
        : "bg-red-500");

  const textColor =
    clampedScore >= 70
      ? "text-emerald-400"
      : clampedScore >= 50
        ? "text-amber-400"
        : "text-red-400";

  return (
    <div className="flex items-center gap-3">
      <span className="w-24 shrink-0 text-xs text-zinc-400 text-right">
        {label}
      </span>
      <div className="flex-1 h-2 rounded-full bg-zinc-800">
        <div
          className={`h-2 rounded-full transition-all ${barColor}`}
          style={{ width: `${clampedScore}%` }}
        />
      </div>
      <span className={`w-8 shrink-0 text-xs font-mono font-semibold ${textColor}`}>
        {clampedScore.toFixed(0)}
      </span>
    </div>
  );
}
