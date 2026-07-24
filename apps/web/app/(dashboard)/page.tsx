import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { agentsResponseSchema, meResponseSchema } from "@/lib/api";
import { fetchBackend } from "@/lib/backend-fetch";
import { t } from "@/lib/strings";

export default async function HomePage() {
  const meResponse = await fetchBackend("/api/auth/me", cookies().toString());
  const me = meResponseSchema.safeParse(await meResponse.json());
  if (!me.success) {
    redirect("/login");
  }

  const agentsResponse = await fetchBackend(
    "/api/agents",
    cookies().toString(),
  );
  const agents = agentsResponseSchema.safeParse(await agentsResponse.json());

  return (
    <div className="p-6">
      <p className="text-lg">
        {t("home.greeting", { name: me.data.data.ownerName })}
      </p>

      {!agents.success || agents.data.data.agents.length === 0 ? (
        <p className="mt-4 text-muted-foreground">{t("home.noAgents")}</p>
      ) : (
        <div className="mt-6 space-y-2">
          {agents.data.data.recentConversations.map((c) => (
            <div
              key={c.id}
              className="flex items-center justify-between rounded-md border p-3"
            >
              <div>
                <p className="text-sm font-medium">{c.buyerName}</p>
                <p className="text-sm text-muted-foreground">
                  {c.lastMessagePreview}
                </p>
              </div>
              {c.unread ? (
                <span className="rounded-full bg-emerald-600 px-2 py-0.5 text-xs text-white">
                  1
                </span>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
