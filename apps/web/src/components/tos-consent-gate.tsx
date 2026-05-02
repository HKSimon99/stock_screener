"use client";

/**
 * TosConsentGate — blocks signed-in users until they accept the current ToS.
 *
 * Behavior:
 *  • Signed-out users: renders children unchanged. ToS only applies to authenticated use.
 *  • Signed-in users: fetches /api/v1/users/me. While loading, renders children
 *    (no flash of modal on every navigation). If the server reports
 *    tos_accepted === false, an opaque overlay locks the app until accepted.
 *  • The current ToS version comes from the server (UserMe.current_tos_version)
 *    and is echoed back on accept — so a server-side bump immediately re-prompts
 *    everyone without a client redeploy.
 *
 * Wire this between QueryClientProvider and ClerkProvider (it depends on both).
 */

import { useState } from "react";
import { useAuth, useUser } from "@clerk/nextjs";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { acceptTos, fetchMe, type UserMe } from "@/lib/api";

const ME_QUERY_KEY = ["users", "me"] as const;

export function TosConsentGate({ children }: { children: React.ReactNode }) {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const { user } = useUser();
  const queryClient = useQueryClient();
  const [submitError, setSubmitError] = useState<string | null>(null);

  const { data: me, isPending } = useQuery<UserMe>({
    queryKey: ME_QUERY_KEY,
    queryFn: async () => {
      const token = await getToken();
      if (!token) throw new Error("not signed in");
      return fetchMe(token);
    },
    enabled: Boolean(isLoaded && isSignedIn),
    // ToS state changes on user action; don't refetch on every focus.
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    retry: 1,
  });

  const accept = useMutation({
    mutationFn: async () => {
      const token = await getToken();
      if (!token) throw new Error("not signed in");
      if (!me) throw new Error("user state not loaded yet");
      return acceptTos({
        bearerToken: token,
        version: me.current_tos_version,
        // Best-effort capture of primary email so we can reach the user about future ToS changes.
        email: user?.primaryEmailAddress?.emailAddress,
      });
    },
    onSuccess: (next) => {
      queryClient.setQueryData(ME_QUERY_KEY, next);
      setSubmitError(null);
    },
    onError: (err) => {
      setSubmitError(err instanceof Error ? err.message : "Failed to record acceptance.");
    },
  });

  // Pass-through: signed-out, Clerk still loading, or /me still in flight.
  if (!isLoaded || !isSignedIn || isPending || !me) {
    return <>{children}</>;
  }

  // User has already accepted the current version → no gate.
  if (me.tos_accepted) {
    return <>{children}</>;
  }

  return (
    <>
      {children}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="tos-modal-title"
        className="fixed inset-0 z-[200] flex items-center justify-center bg-black/80 px-4 py-8 backdrop-blur-sm"
      >
        <div className="relative w-full max-w-lg rounded-2xl border border-white/10 bg-[oklch(0.13_0.01_240)] p-6 shadow-2xl">
          <div className="text-[0.65rem] uppercase tracking-[0.18em] text-faint">
            Version {me.current_tos_version}
          </div>
          <h2
            id="tos-modal-title"
            className="mt-2 font-heading text-2xl uppercase tracking-[0.04em] text-white"
          >
            Terms of Service
          </h2>

          <div className="mt-4 space-y-3 text-sm leading-6 text-quiet">
            <p>
              Consensus Signal Research provides ranking and chart data for US and Korean
              equities. The information is for research only — it is <span className="text-white">not</span> investment
              advice, a recommendation, or an offer to buy or sell securities.
            </p>
            <p>
              Data sources include yfinance, SEC EDGAR, OpenDART, and KIS Developers. We do
              our best to keep data fresh and accurate, but we make no warranty of completeness
              or correctness. You alone are responsible for any trading decisions.
            </p>
            <p>
              By continuing, you agree to use the service for personal research, not to scrape
              or redistribute the data, and to accept that the service may change or be
              discontinued without notice.
            </p>
          </div>

          {submitError && (
            <div className="mt-4 rounded-lg border border-[oklch(0.68_0.18_28_/_0.4)] bg-[oklch(0.31_0.06_28_/_0.16)] px-3 py-2 text-xs text-[oklch(0.89_0.04_24)]">
              {submitError}
            </div>
          )}

          <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={() => {
                // We don't have a server-side decline endpoint; signing out is the
                // cleanest way to refuse without leaving a half-authenticated state.
                window.location.href = "/sign-out";
              }}
              className="rounded-full border border-white/10 px-5 py-2 text-xs uppercase tracking-[0.12em] text-faint hover:text-white"
            >
              Decline & sign out
            </button>
            <button
              type="button"
              disabled={accept.isPending}
              onClick={() => accept.mutate()}
              className="rounded-full bg-white px-5 py-2 text-xs font-medium uppercase tracking-[0.12em] text-black hover:bg-white/90 disabled:opacity-50"
            >
              {accept.isPending ? "Recording…" : "Accept & continue"}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
