import { fetchAlerts, type AlertsResponse } from "@/lib/api";
import { AlertsClient } from "@/app/app/alerts/_components/alerts-client";

export default async function AppAlertsPage() {
  let initialData: AlertsResponse | null = null;

  try {
    initialData = await fetchAlerts({
      days: 30,
      limit: 100,
    });
  } catch {
    // Client-side query handles recovery.
  }

  return <AlertsClient initialData={initialData} />;
}
