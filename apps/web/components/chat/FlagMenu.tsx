"use client";

import { MoreVertical } from "lucide-react";
import { useRouter } from "next/navigation";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { apiFetch, flagResponseSchema } from "@/lib/api";
import { t } from "@/lib/strings";

export function FlagMenu({
  conversationId,
  flagged,
}: {
  conversationId: string;
  flagged: boolean;
}) {
  const router = useRouter();

  async function toggleFlag(): Promise<void> {
    await apiFetch(
      `/api/conversations/${conversationId}/flag`,
      flagResponseSchema,
      {
        method: "POST",
        body: JSON.stringify({ flagged: !flagged }),
      },
    );
    router.refresh();
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={t(flagged ? "convos.unflagAction" : "convos.flagAction")}
          className="flex h-11 w-11 items-center justify-center"
        >
          <MoreVertical className="h-4 w-4" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => void toggleFlag()}>
          {t(flagged ? "convos.unflagAction" : "convos.flagAction")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
