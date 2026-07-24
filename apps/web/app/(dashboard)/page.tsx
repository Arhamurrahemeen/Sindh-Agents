import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { agentsResponseSchema, meResponseSchema } from "@/lib/api";
import { fetchBackend } from "@/lib/backend-fetch";
import { t } from "@/lib/strings";
import { cn } from "@/lib/utils";

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
        <>
          <h2 className="mt-6 text-sm font-medium text-muted-foreground">
            {t("home.agentsTitle")}
          </h2>
          <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {agents.data.data.agents.map((agent) => (
              <Card key={agent.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle>{agent.nameUrdu}</CardTitle>
                    <span
                      className={cn(
                        "h-2.5 w-2.5 rounded-full",
                        agent.status === "live"
                          ? "bg-emerald-600"
                          : "bg-muted-foreground",
                      )}
                      aria-hidden
                    />
                  </div>
                </CardHeader>
                <CardContent className="space-y-2">
                  <p className="text-sm text-muted-foreground">
                    {t(
                      agent.status === "live"
                        ? "home.agentStatus.live"
                        : "home.agentStatus.paused",
                    )}
                  </p>
                  <p className="text-sm">
                    {t("home.msgsToday", { n: String(agent.messagesToday) })}
                  </p>
                  <Link
                    href="/conversations"
                    className="block text-sm font-medium text-emerald-700 hover:underline"
                  >
                    {t("home.viewAll")}
                  </Link>
                </CardContent>
              </Card>
            ))}
          </div>

          <h2 className="mt-6 text-sm font-medium text-muted-foreground">
            {t("home.recentConvos")}
          </h2>
          <div className="mt-2 space-y-2">
            {agents.data.data.recentConversations.map((c) => (
              <Link
                key={c.id}
                href={`/conversations/${c.id}`}
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
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
