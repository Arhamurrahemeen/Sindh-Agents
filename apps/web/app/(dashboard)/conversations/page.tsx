import Link from "next/link";
import { cookies } from "next/headers";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { FlagMenu } from "@/components/chat/FlagMenu";
import { conversationsResponseSchema } from "@/lib/api";
import { fetchBackend } from "@/lib/backend-fetch";
import { t, type StringKey } from "@/lib/strings";
import { cn } from "@/lib/utils";

const TABS = ["all", "unread", "flagged"] as const;
type Tab = (typeof TABS)[number];

const TAB_LABEL: Record<Tab, StringKey> = {
  all: "convos.tabAll",
  unread: "convos.tabUnread",
  flagged: "convos.tabFlagged",
};

function isTab(value: string | undefined): value is Tab {
  return TABS.includes(value as Tab);
}

export default async function ConversationsPage({
  searchParams,
}: {
  searchParams: { tab?: string; q?: string };
}) {
  const tab: Tab = isTab(searchParams.tab) ? searchParams.tab : "all";
  const q = searchParams.q ?? "";

  const query = new URLSearchParams({ tab });
  if (q) query.set("q", q);

  const response = await fetchBackend(
    `/api/conversations?${query.toString()}`,
    cookies().toString(),
  );
  const parsed = conversationsResponseSchema.safeParse(await response.json());
  const conversations = parsed.success ? parsed.data.data.conversations : [];

  return (
    <div className="p-4">
      {/* Native GET form — submits on Enter, no client JS needed for search. */}
      <form className="mb-4">
        <input type="hidden" name="tab" value={tab} />
        <Input
          type="search"
          name="q"
          defaultValue={q}
          placeholder={t("convos.searchPlaceholder")}
        />
      </form>

      <div className="mb-4 flex gap-2">
        {TABS.map((tabOption) => (
          <Link
            key={tabOption}
            href={`/conversations?tab=${tabOption}${q ? `&q=${encodeURIComponent(q)}` : ""}`}
            className={cn(
              "rounded-md px-3 py-1 text-sm",
              tab === tabOption
                ? "bg-emerald-600 text-white"
                : "bg-muted text-muted-foreground",
            )}
          >
            {t(TAB_LABEL[tabOption])}
          </Link>
        ))}
      </div>

      {conversations.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("convos.empty")}</p>
      ) : (
        <div className="space-y-2">
          {conversations.map((c) => (
            <div
              key={c.id}
              className="flex items-center justify-between rounded-md border p-3"
            >
              <Link href={`/conversations/${c.id}`} className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{c.buyerName}</p>
                <p className="truncate text-xs text-muted-foreground">
                  {c.lastMessagePreview}
                </p>
              </Link>
              <div className="flex shrink-0 items-center gap-2 pl-2">
                {c.flagged ? (
                  <Badge variant="destructive">
                    {t("convos.flaggedBadge")}
                  </Badge>
                ) : null}
                {c.unread ? (
                  <span className="h-2 w-2 rounded-full bg-emerald-600" />
                ) : null}
                <FlagMenu conversationId={c.id} flagged={c.flagged} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
