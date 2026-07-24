"use client";

import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { ToolCallRow } from "@/components/chat/ToolCallRow";
import { apiFetch, flagResponseSchema, type AuditResponse } from "@/lib/api";
import { t } from "@/lib/strings";

type AuditDrawerProps = {
  open: boolean;
  basePath: string;
  conversationId: string;
  audit: AuditResponse["data"] | null;
};

export function AuditDrawer({
  open,
  basePath,
  conversationId,
  audit,
}: AuditDrawerProps) {
  const router = useRouter();

  function handleOpenChange(next: boolean): void {
    if (!next) {
      router.push(basePath);
    }
  }

  async function handleFlag(): Promise<void> {
    await apiFetch(
      `/api/conversations/${conversationId}/flag`,
      flagResponseSchema,
      {
        method: "POST",
        body: JSON.stringify({ flagged: true }),
      },
    );
    router.refresh();
  }

  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent side="right" className="overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle>{t("audit.title")}</SheetTitle>
        </SheetHeader>

        {audit === null ? (
          <p className="px-4 pb-4 text-sm text-muted-foreground">
            {t("audit.notFound")}
          </p>
        ) : (
          <div className="space-y-4 px-4 pb-4 text-sm">
            <div>
              <p className="text-xs text-muted-foreground">
                Buyer&apos;s message
              </p>
              <p className="font-mono">{audit.buyerMessage.text}</p>
            </div>

            <p>
              {t("audit.understanding", { parsedIntent: audit.parsedIntent })}
            </p>

            <div>
              <p className="mb-2 text-xs text-muted-foreground">
                {t("audit.toolsTitle")}
              </p>
              <div className="space-y-2">
                {audit.toolCalls.map((toolCall, index) => (
                  // Static list from a single audit fetch — never reordered, no stable id exists.
                  <ToolCallRow key={index} toolCall={toolCall} />
                ))}
              </div>
            </div>

            <div>
              <p className="text-xs text-muted-foreground">
                {t("audit.replyTitle")}
              </p>
              <p>{audit.agentReply.text}</p>
            </div>

            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>
                {t("audit.timingTitle")}: {audit.totalLatencyMs}ms
              </span>
              <Badge variant="secondary">{audit.model}</Badge>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => void handleFlag()}
            >
              {t("audit.flagButton")}
            </Button>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
