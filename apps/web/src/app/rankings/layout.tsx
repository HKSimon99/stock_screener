import { AppNav } from "@/components/app-nav";
import { LegalFooter } from "@/components/legal-footer";

export default function PublicRankingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen">
      <AppNav />
      {children}
      <LegalFooter />
    </div>
  );
}
