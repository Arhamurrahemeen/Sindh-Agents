import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { InventoryUploadForm } from "@/components/inventory/InventoryUploadForm";
import { meResponseSchema } from "@/lib/api";
import { fetchBackend } from "@/lib/backend-fetch";
import { t } from "@/lib/strings";

export default async function InventoryPage() {
  const meResponse = await fetchBackend("/api/auth/me", cookies().toString());
  const me = meResponseSchema.safeParse(await meResponse.json());
  if (!me.success) {
    redirect("/login");
  }

  return (
    <div className="space-y-4 p-6">
      <Link href="/" className="text-sm text-muted-foreground hover:underline">
        {t("inventory.backToHome")}
      </Link>
      <h1 className="text-lg font-medium">{t("inventory.title")}</h1>
      <InventoryUploadForm />
    </div>
  );
}
