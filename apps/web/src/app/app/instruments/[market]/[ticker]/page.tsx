import {
  fetchInstrument,
  fetchInstrumentChart,
  type InstrumentChart,
  type InstrumentDetail,
} from "@/lib/api";
import { InstrumentDetailClient } from "@/app/app/instruments/[market]/[ticker]/_components/instrument-detail-client";

interface PageProps {
  params: Promise<{ market: string; ticker: string }>;
}

export default async function CanonicalInstrumentPage({ params }: PageProps) {
  const resolved = await params;
  const ticker = resolved.ticker;
  const market = resolved.market === "KR" ? "KR" : "US";

  let initialData: InstrumentDetail | null = null;
  let initialChartData: InstrumentChart | null = null;

  const [instrumentResult, chartResult] = await Promise.allSettled([
    fetchInstrument(ticker, market),
    fetchInstrumentChart(ticker, market, {
      interval: "1d",
      range_days: 365,
      include_indicators: true,
    }),
  ]);

  if (instrumentResult.status === "fulfilled") {
    initialData = instrumentResult.value;
  }

  if (chartResult.status === "fulfilled") {
    initialChartData = chartResult.value;
  }

  return (
    <InstrumentDetailClient
      ticker={ticker}
      market={market}
      initialData={initialData}
      initialChartData={initialChartData}
    />
  );
}
