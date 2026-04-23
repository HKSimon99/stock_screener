export default function RankingsLoading() {
  return (
    <div id="content" className="app-shell py-4 sm:py-6">
      <section className="relative overflow-hidden rounded-[2.4rem] border border-[oklch(0.76_0.04_88)] bg-[oklch(0.94_0.018_88)] px-4 py-5 shadow-[0_30px_120px_oklch(0.08_0.015_250_/_0.34)] sm:px-6 sm:py-7">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_12%_12%,oklch(0.82_0.13_82_/_0.22),transparent_28%),radial-gradient(circle_at_82%_8%,oklch(0.7_0.08_195_/_0.18),transparent_25%)]" />
        <div className="relative grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(22rem,0.7fr)] xl:items-end">
          <div>
            <div className="h-8 w-52 animate-pulse rounded-full bg-black/10" />
            <div className="mt-5 h-24 w-full max-w-3xl animate-pulse rounded-[2rem] bg-black/10 sm:h-32" />
            <div className="mt-5 h-5 w-full max-w-2xl animate-pulse rounded-full bg-black/10" />
          </div>
          <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
            {Array.from({ length: 3 }).map((_, index) => (
              <div
                key={index}
                className="rounded-[1.5rem] border border-[oklch(0.8_0.03_88)] bg-white/58 p-4"
              >
                <div className="h-3 w-24 animate-pulse rounded-full bg-black/10" />
                <div className="mt-3 h-9 w-28 animate-pulse rounded-xl bg-black/10" />
                <div className="mt-2 h-3 w-36 animate-pulse rounded-full bg-black/10" />
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mt-5 surface-panel rounded-[2rem] px-4 py-4 sm:px-5">
        <div className="h-8 w-60 animate-pulse rounded-xl bg-white/10" />
        <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-6">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="h-24 animate-pulse rounded-[1.35rem] bg-white/8" />
          ))}
        </div>
      </section>

      <section className="mt-5 rounded-[2rem] border border-[oklch(0.82_0.03_88)] bg-[oklch(0.94_0.018_88_/_0.82)] p-4 sm:p-5">
        <div className="h-10 w-72 animate-pulse rounded-xl bg-black/10" />
        <div className="mt-4 grid gap-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div
              key={index}
              className="h-36 animate-pulse rounded-[1.6rem] border border-[oklch(0.8_0.03_88)] bg-white/70"
            />
          ))}
        </div>
      </section>
    </div>
  );
}
