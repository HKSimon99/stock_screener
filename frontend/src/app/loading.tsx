export default function RootLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="space-y-4">
        <div className="surface-panel rounded-[1.65rem] h-12 w-48 animate-pulse" />
        <div className="surface-panel rounded-[1.65rem] h-8 w-64 animate-pulse" />
      </div>
    </div>
  );
}
