import { z } from "zod";

const errorEnvelopeSchema = z.object({
  ok: z.literal(false),
  error: z.object({
    code: z.string(),
    message: z.string(),
    messageUrdu: z.string().optional(),
    field: z.string().optional(),
    requestId: z.string(),
  }),
});

export class ApiError extends Error {
  code: string;
  messageUrdu: string | undefined;
  field: string | undefined;
  requestId: string;

  constructor(body: z.infer<typeof errorEnvelopeSchema>["error"]) {
    super(body.message);
    this.code = body.code;
    this.messageUrdu = body.messageUrdu;
    this.field = body.field;
    this.requestId = body.requestId;
  }
}

export async function apiFetch<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "content-type": "application/json", ...init?.headers },
  });
  const json: unknown = await response.json();

  if (!response.ok) {
    const parsed = errorEnvelopeSchema.safeParse(json);
    if (!parsed.success) {
      throw new ApiError({
        code: "UNKNOWN",
        message: "Unexpected error response",
        requestId: "",
      });
    }
    throw new ApiError(parsed.data.error);
  }

  const parsed = schema.safeParse(json);
  if (!parsed.success) {
    throw new ApiError({
      code: "INVALID_RESPONSE",
      message: parsed.error.message,
      requestId: "",
    });
  }
  return parsed.data;
}

export const sendOtpResponseSchema = z.object({
  ok: z.literal(true),
  data: z.object({
    expiresInSeconds: z.number(),
    resendAvailableInSeconds: z.number(),
  }),
});
export type SendOtpResponse = z.infer<typeof sendOtpResponseSchema>;

export const verifyOtpResponseSchema = z.object({
  ok: z.literal(true),
  data: z.object({
    smeId: z.string(),
    smeName: z.string(),
    ownerName: z.string(),
  }),
});
export type VerifyOtpResponse = z.infer<typeof verifyOtpResponseSchema>;

export const meResponseSchema = z.object({
  ok: z.literal(true),
  data: z.object({
    smeId: z.string(),
    smeName: z.string(),
    ownerName: z.string(),
    phone: z.string(),
  }),
});
export type MeResponse = z.infer<typeof meResponseSchema>;

export const logoutResponseSchema = z.object({ ok: z.literal(true) });

export const agentsResponseSchema = z.object({
  ok: z.literal(true),
  data: z.object({
    smeName: z.string(),
    ownerName: z.string(),
    agents: z.array(
      z.object({
        id: z.string(),
        name: z.string(),
        nameUrdu: z.string(),
        status: z.enum(["live", "paused"]),
        messagesToday: z.number(),
        lastActive: z.string().nullable(),
      }),
    ),
    recentConversations: z.array(
      z.object({
        id: z.string(),
        buyerName: z.string(),
        lastMessagePreview: z.string(),
        lastMessageAt: z.string(),
        unread: z.boolean(),
      }),
    ),
  }),
});
export type AgentsResponse = z.infer<typeof agentsResponseSchema>;

export const widgetInboundResponseSchema = z.object({
  ok: z.literal(true),
  data: z.object({ accepted: z.literal(true), messageId: z.string() }),
});

export const widgetOutboundResponseSchema = z.object({
  messages: z.array(
    z.object({
      id: z.string(),
      timestamp: z.string(),
      text: z.object({ body: z.string() }),
    }),
  ),
  hasMore: z.boolean(),
});
export type WidgetOutboundResponse = z.infer<
  typeof widgetOutboundResponseSchema
>;
