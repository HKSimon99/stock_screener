import { auth } from "@clerk/nextjs/server";
import { AppNav } from "@/components/app-nav";

export default async function ProductAppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  await auth.protect();

  return (
    <div className="min-h-screen pb-24 md:pb-12">
      <AppNav />
      {children}
    </div>
  );
}
