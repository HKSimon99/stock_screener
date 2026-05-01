import { redirect } from "next/navigation";

export default async function AppRankingsRedirect({
  searchParams,
}: {
  searchParams: Promise<Record<string, string>>;
}) {
  const sp = await searchParams;
  const qs = new URLSearchParams(sp).toString();
  redirect(qs ? `/rankings?${qs}` : "/rankings");
}
