"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  ApiError,
  apiFetch,
  widgetInboundResponseSchema,
  widgetOutboundResponseSchema,
} from "@/lib/api";
import { t } from "@/lib/strings";

type ChatMessage = {
  id: string;
  sender: "buyer" | "agent";
  text: string;
};

const WA_ID_STORAGE_KEY = "sindh-agents-widget-wa-id";
const PHONE_NUMBER_ID = "sindh-agents-demo-widget";
const DISPLAY_PHONE_NUMBER = "+10000000000";

function getOrCreateWaId(): string {
  const existing = localStorage.getItem(WA_ID_STORAGE_KEY);
  if (existing) return existing;
  const next = crypto.randomUUID();
  localStorage.setItem(WA_ID_STORAGE_KEY, next);
  return next;
}

export function SindhAgentsWidget() {
  const [open, setOpen] = useState(false);
  const [waId, setWaId] = useState<string | null>(null);
  const [name, setName] = useState<string | null>(null);
  const [nameInput, setNameInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const lastMessageIdRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    setWaId(getOrCreateWaId());
  }, []);

  useEffect(() => {
    if (!waId || !name) return;
    let cancelled = false;

    async function poll(): Promise<void> {
      while (!cancelled) {
        try {
          const params = new URLSearchParams({ wa_id: waId as string });
          if (lastMessageIdRef.current)
            params.set("after", lastMessageIdRef.current);
          const result = await apiFetch(
            `/api/widget/outbound?${params.toString()}`,
            widgetOutboundResponseSchema,
          );
          const last = result.messages[result.messages.length - 1];
          if (last) {
            lastMessageIdRef.current = last.id;
            setMessages((prev) => [
              ...prev,
              ...result.messages.map((m) => ({
                id: m.id,
                sender: "agent" as const,
                text: m.text.body,
              })),
            ]);
          }
        } catch {
          await new Promise((resolve) => setTimeout(resolve, 2000));
        }
      }
    }

    void poll();
    return () => {
      cancelled = true;
    };
    // why: no cleanup beyond the cancelled flag — the in-flight fetch simply
    // finishes and the loop exits on its next iteration check.
  }, [waId, name]);

  function handleNameSubmit(): void {
    if (!nameInput.trim()) return;
    setName(nameInput.trim());
    setMessages([
      { id: "greeting", sender: "agent", text: t("widget.greeting") },
    ]);
  }

  async function handleSend(): Promise<void> {
    if (!inputText.trim() || !waId || !name) return;
    const text = inputText.trim();
    const clientMessageId = crypto.randomUUID();
    setMessages((prev) => [
      ...prev,
      { id: clientMessageId, sender: "buyer", text },
    ]);
    setInputText("");
    setError(null);

    try {
      await apiFetch("/api/widget/inbound", widgetInboundResponseSchema, {
        method: "POST",
        headers: { "Idempotency-Key": clientMessageId },
        body: JSON.stringify({
          messaging_product: "widget",
          metadata: {
            display_phone_number: DISPLAY_PHONE_NUMBER,
            phone_number_id: PHONE_NUMBER_ID,
          },
          contacts: [{ profile: { name }, wa_id: waId }],
          messages: [
            {
              from: waId,
              id: clientMessageId,
              timestamp: String(Math.floor(Date.now() / 1000)),
              text: { body: text },
              type: "text",
            },
          ],
        }),
      });
    } catch (err) {
      setError(
        err instanceof ApiError
          ? (err.messageUrdu ?? t("widget.offlineError"))
          : t("widget.offlineError"),
      );
    }
  }

  return (
    <div className="fixed bottom-4 right-4 z-50">
      {!open ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="flex size-14 items-center justify-center rounded-full bg-emerald-600 text-2xl text-white shadow-lg hover:bg-emerald-700"
          aria-label={t("widget.greeting")}
        >
          💬
        </button>
      ) : (
        <div className="flex h-[480px] w-80 flex-col overflow-hidden rounded-lg border bg-background shadow-xl">
          <div className="flex items-center justify-between bg-emerald-600 p-3 text-white">
            <span className="text-sm font-medium">Sindh Agents</span>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close"
            >
              ✕
            </button>
          </div>

          {!name ? (
            <div className="flex flex-1 flex-col justify-center gap-3 p-4">
              <label htmlFor="widget-name" className="text-sm">
                {t("widget.namePrompt")}
              </label>
              <Input
                id="widget-name"
                value={nameInput}
                onChange={(e) => setNameInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleNameSubmit()}
              />
              <Button
                onClick={handleNameSubmit}
                className="bg-emerald-600 hover:bg-emerald-700"
              >
                {t("widget.nameSubmit")}
              </Button>
            </div>
          ) : (
            <>
              <div className="flex-1 space-y-2 overflow-y-auto p-3">
                {messages.map((m) => (
                  <div
                    key={m.id}
                    className={
                      m.sender === "buyer"
                        ? "ml-auto max-w-[85%] rounded-lg bg-emerald-50 p-2 text-sm"
                        : "mr-auto max-w-[85%] rounded-lg bg-muted p-2 text-sm"
                    }
                  >
                    {m.text}
                  </div>
                ))}
                {error ? (
                  <p className="text-xs text-destructive">{error}</p>
                ) : null}
              </div>
              <form
                className="flex gap-2 border-t p-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  void handleSend();
                }}
              >
                <Input
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  placeholder={t("widget.placeholder")}
                />
                <Button
                  type="submit"
                  className="bg-emerald-600 hover:bg-emerald-700"
                >
                  {t("widget.send")}
                </Button>
              </form>
            </>
          )}
        </div>
      )}
    </div>
  );
}
