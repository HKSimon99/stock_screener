export default function RankingsLoading() {
  return (
    <div id="content" className="app-shell">
      <div className="space-y-4">
        {/* Header skeleton */}
        <div className="surface-panel rounded-[1.65rem] px-4 py-4 sm:px-5">
          <div className="space-y-3">
            <div className="h-6 w-32 animate-pulse bg-white/10 rounded" />
            <div className="h-10 w-48 animate-pulse bg-white/10 rounded" />
          </div>
        </div>

        {/* Filter skeleton */}
        <div className="surface-panel rounded-[1.65rem] px-4 py-4 sm:px-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="h-10 w-40 animate-pulse bg-white/10 rounded-full" />
            <div className="h-10 flex-1 animate-pulse bg-white/10 rounded-full" />
          </div>
        </div>

        {/* List skeleton */}
        <div className="space-y-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="surface-panel rounded-[1.65rem] px-4 py-4 sm:px-5"
            >
              <div className="flex items-center gap-4">
                <div className="h-5 w-12 animate-pulse bg-white/10 rounded" />
                <div className="flex-1 space-y-2">
                  <div className="h-5 w-32 animate-pulse bg-white/10 rounded" />
                  <div className="h-4 w-48 animate-pulse bg-white/10 rounded" />
                </div>
                <div className="space-y-2 text-right">
                  <div className="h-5 w-16 animate-pulse bg-white/10 rounded" />
                  <div className="h-4 w-20 animate-pulse bg-white/10 rounded" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
