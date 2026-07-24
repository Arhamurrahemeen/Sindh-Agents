import { Search } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/utils";
import { t } from "@/lib/strings";

type MessageBubbleProps = {
  message: {
    id: string;
    sender: "buyer" | "agent";
    text: string;
    timestamp: string;
    auditMessageId?: string | null | undefined;
  };
  conversationId: string;
};

export function MessageBubble({ message, conversationId }: MessageBubbleProps) {
  const isAgent = message.sender === "agent";
  const time = new Date(message.timestamp).toLocaleTimeString("en-PK", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Karachi",
  });

  return (
    <div className={cn("flex", isAgent ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-lg px-3 py-2 text-sm",
          isAgent
            ? "bg-emerald-50 text-emerald-950"
            : "bg-white ring-1 ring-foreground/10",
        )}
      >
        {/* api-contract.md §2.3 — text is rendered verbatim, no client reformatting */}
        <p className="whitespace-pre-wrap">{message.text}</p>
        <div className="mt-1 flex items-center gap-1 text-[10px] text-muted-foreground">
          <span>{time}</span>
          {isAgent && message.auditMessageId ? (
            <Link
              href={`/conversations/${conversationId}?audit=${message.auditMessageId}`}
              aria-label={t("convo.auditTooltip")}
              title={t("convo.auditTooltip")}
              className="flex h-11 w-11 items-center justify-center"
            >
              <Search className="h-3.5 w-3.5" />
            </Link>
          ) : null}
        </div>
      </div>
    </div>
  );
}
