import { cookies } from "next/headers";
import { notFound } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { AuditDrawer } from "@/components/chat/AuditDrawer";
import { MessageBubble } from "@/components/chat/MessageBubble";
import {
  auditResponseSchema,
  conversationDetailResponseSchema,
} from "@/lib/api";
import { fetchBackend } from "@/lib/backend-fetch";
import { t } from "@/lib/strings";

export default async function ConversationDetailPage({
  params,
  searchParams,
}: {
  params: { id: string };
  searchParams: { audit?: string | string[] };
}) {
  const response = await fetchBackend(
    `/api/conversations/${params.id}`,
    cookies().toString(),
  );
  if (response.status === 404) {
    notFound();
  }
  const parsed = conversationDetailResponseSchema.safeParse(
    await response.json(),
  );
  if (!parsed.success) {
    notFound();
  }
  const convo = parsed.data.data;

  const auditMessageId = Array.isArray(searchParams.audit)
    ? searchParams.audit[0]
    : searchParams.audit;

  let audit = null;
  if (auditMessageId) {
    const auditResponse = await fetchBackend(
      `/api/audit/${auditMessageId}`,
      cookies().toString(),
    );
    const auditParsed = auditResponseSchema.safeParse(
      await auditResponse.json(),
    );
    if (auditParsed.success) {
      audit = auditParsed.data.data;
    }
  }

  return (
    <div className="flex h-[calc(100vh-65px)] flex-col">
      <div className="border-b p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium">{convo.buyer.name}</p>
            <p className="text-xs text-muted-foreground">{convo.buyer.phone}</p>
          </div>
          <Badge variant="secondary">
            {t("convo.agentPill", { agentNameUrdu: convo.agent.nameUrdu })}
          </Badge>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          {t("convo.readOnlyBanner")}
        </p>
      </div>

      <ScrollArea className="flex-1 p-4">
        <div className="space-y-3">
          {convo.messages.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("convo.empty")}</p>
          ) : (
            convo.messages.map((m) => (
              <MessageBubble key={m.id} message={m} conversationId={convo.id} />
            ))
          )}
        </div>
      </ScrollArea>

      <AuditDrawer
        open={Boolean(auditMessageId)}
        basePath={`/conversations/${convo.id}`}
        conversationId={convo.id}
        audit={audit}
      />
    </div>
  );
}
