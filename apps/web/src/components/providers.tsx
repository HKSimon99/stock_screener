"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { useState } from "react";

/**
 * Providers — wraps the app in TanStack Query context.
 *
 * QueryClient defaults (tuned for a financial research tool):
 *  • staleTime  60 s  — data stays fresh for 1 minute before a background refetch
 *  • gcTime     5 min — unused cache entries held for 5 minutes (default is 5 min, explicit here)
 *  • retry      1     — one automatic retry on server error, avoids hammering down APIs
 *  • refetchOnWindowFocus false — no surprise refetch when the user alt-tabs back
 *
 * DevTools are included in dev only (tree-shaken in production builds).
 */

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,          // 1 min — fresh enough for rankings/scores
        gcTime: 5 * 60_000,         // 5 min — keep cache warm during a session
        retry: 1,                   // one retry for transient 5xx
        refetchOnWindowFocus: false, // trading research — no surprise background loads
      },
    },
  });
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(makeQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {process.env.NODE_ENV === "development" && (
        <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-right" />
      )}
    </QueryClientProvider>
  );
}
