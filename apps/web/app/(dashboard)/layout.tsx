import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { meResponseSchema } from "@/lib/api";
import { fetchBackend } from "@/lib/backend-fetch";
import { DashboardHeader } from "@/components/dashboard-header";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const response = await fetchBackend("/api/auth/me", cookies().toString());
  const parsed = meResponseSchema.safeParse(await response.json());
  if (!parsed.success) {
    redirect("/login");
  }

  return (
    <div className="flex min-h-screen flex-col">
      <DashboardHeader smeName={parsed.data.data.smeName} />
      <main className="flex-1">{children}</main>
    </div>
  );
}
