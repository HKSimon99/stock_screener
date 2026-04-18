"use client";

import { Analytics, type BeforeSendEvent } from "@vercel/analytics/react";
import { SpeedInsights } from "@vercel/speed-insights/next";

export function Observability() {
  return (
    <>
      <Analytics
        beforeSend={(event: BeforeSendEvent) => {
          const url = new URL(event.url);
          url.search = "";
          return {
            ...event,
            url: url.toString(),
          };
        }}
      />
      <SpeedInsights />
    </>
  );
}
