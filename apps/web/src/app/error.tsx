"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="surface-panel rounded-[1.65rem] max-w-md w-full p-6 sm:p-8">
        <h1 className="text-2xl font-heading font-bold text-white mb-2">
          Something went wrong
        </h1>
        <p className="text-faint mb-6">
          {error.message || "An unexpected error occurred. Please try again."}
        </p>
        {error.digest && (
          <p className="text-xs text-faint/60 mb-4 font-mono">
            Error ID: {error.digest}
          </p>
        )}
        <button
          onClick={() => reset()}
          className="w-full rounded-full border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-white/10"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
