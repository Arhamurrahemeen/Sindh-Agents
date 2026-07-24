"use client";

import { useRouter } from "next/navigation";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { apiFetch, logoutResponseSchema } from "@/lib/api";
import { t } from "@/lib/strings";

function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function DashboardHeader({ smeName }: { smeName: string }) {
  const router = useRouter();

  async function handleLogout(): Promise<void> {
    await apiFetch("/api/auth/logout", logoutResponseSchema, {
      method: "POST",
    });
    router.push("/login");
    router.refresh();
  }

  return (
    <header className="flex items-center justify-between border-b p-4">
      <span className="font-medium">{smeName}</span>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button type="button" aria-label={t("header.logout")}>
            <Avatar>
              <AvatarFallback>{initials(smeName)}</AvatarFallback>
            </Avatar>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => void handleLogout()}>
            {t("header.logout")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
