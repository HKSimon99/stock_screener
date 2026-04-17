export default function InstrumentLoading() {
  return (
    <div id="content" className="app-shell space-y-4">
      {/* Header skeleton */}
      <div className="surface-panel rounded-[1.65rem] px-4 py-4 sm:px-5">
        <div className="space-y-3">
          <div className="h-6 w-20 animate-pulse bg-white/10 rounded" />
          <div className="h-10 w-48 animate-pulse bg-white/10 rounded" />
          <div className="h-5 w-32 animate-pulse bg-white/10 rounded" />
        </div>
      </div>

      {/* Key metrics skeleton */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="surface-panel rounded-[1.65rem] px-4 py-4"
          >
            <div className="space-y-2">
              <div className="h-4 w-20 animate-pulse bg-white/10 rounded" />
              <div className="h-6 w-24 animate-pulse bg-white/10 rounded" />
            </div>
          </div>
        ))}
      </div>

      {/* Chart skeleton */}
      <div className="surface-panel rounded-[1.65rem] px-4 py-4 sm:px-5">
        <div className="space-y-3">
          <div className="h-6 w-32 animate-pulse bg-white/10 rounded" />
          <div className="h-64 w-full animate-pulse bg-white/10 rounded" />
        </div>
      </div>

      {/* Analysis skeleton */}
      <div className="surface-panel rounded-[1.65rem] px-4 py-4 sm:px-5">
        <div className="space-y-3">
          <div className="h-6 w-40 animate-pulse bg-white/10 rounded" />
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-4 w-full animate-pulse bg-white/10 rounded" />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
