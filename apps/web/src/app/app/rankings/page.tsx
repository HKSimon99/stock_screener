import { redirect } from "next/navigation";

export default function AppRankingsRedirect({
  searchParams,
}: {
  searchParams: Promise<Record<string, string>>;
}) {
  void searchParams;
  redirect("/rankings");
}
