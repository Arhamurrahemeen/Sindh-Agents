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

async function parseApiResponse<T>(
  response: Response,
  schema: z.ZodType<T>,
): Promise<T> {
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

export async function apiFetch<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "content-type": "application/json", ...init?.headers },
  });
  return parseApiResponse(response, schema);
}

export async function apiFetchFormData<T>(
  path: string,
  schema: z.ZodType<T>,
  formData: FormData,
): Promise<T> {
  // No content-type header — the browser sets multipart/form-data with the
  // correct boundary itself. apiFetch() can't be reused here: it always
  // forces content-type: application/json.
  const response = await fetch(path, { method: "POST", body: formData });
  return parseApiResponse(response, schema);
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

export const conversationsResponseSchema = z.object({
  ok: z.literal(true),
  data: z.object({
    conversations: z.array(
      z.object({
        id: z.string(),
        buyerName: z.string(),
        buyerPhone: z.string(),
        lastMessagePreview: z.string(),
        lastMessageAt: z.string(),
        unread: z.boolean(),
        flagged: z.boolean(),
        agentName: z.string(),
      }),
    ),
    total: z.number(),
    nextCursor: z.string().nullable(),
  }),
});
export type ConversationsResponse = z.infer<typeof conversationsResponseSchema>;

export const conversationDetailResponseSchema = z.object({
  ok: z.literal(true),
  data: z.object({
    id: z.string(),
    buyer: z.object({
      name: z.string(),
      phone: z.string(),
      firstSeenAt: z.string(),
    }),
    agent: z.object({
      id: z.string(),
      nameUrdu: z.string(),
    }),
    messages: z.array(
      z.object({
        id: z.string(),
        sender: z.enum(["buyer", "agent"]),
        text: z.string(),
        textOriginal: z.string().nullable().optional(),
        timestamp: z.string(),
        auditMessageId: z.string().nullable().optional(),
      }),
    ),
  }),
});
export type ConversationDetailResponse = z.infer<
  typeof conversationDetailResponseSchema
>;

export const flagResponseSchema = z.object({
  ok: z.literal(true),
  data: z.object({ id: z.string(), flagged: z.boolean() }),
});
export type FlagResponse = z.infer<typeof flagResponseSchema>;

export const auditResponseSchema = z.object({
  ok: z.literal(true),
  data: z.object({
    messageId: z.string(),
    buyerMessage: z.object({ text: z.string(), timestamp: z.string() }),
    parsedIntent: z.string(),
    toolCalls: z.array(
      z.object({
        name: z.string(),
        inputs: z.record(z.string(), z.unknown()),
        outputs: z.unknown(),
        latencyMs: z.number(),
      }),
    ),
    agentReply: z.object({ text: z.string(), timestamp: z.string() }),
    model: z.string(),
    totalLatencyMs: z.number(),
  }),
});
export type AuditResponse = z.infer<typeof auditResponseSchema>;

export const widgetInboundResponseSchema = z.object({
  ok: z.literal(true),
  data: z.object({ accepted: z.literal(true), messageId: z.string() }),
});

export const reingestResponseSchema = z.object({
  ok: z.literal(true),
  data: z.object({
    snapshotId: z.string(),
    itemCount: z.number(),
    ingestedAt: z.string(),
    isNoop: z.boolean(),
  }),
});
export type ReingestResponse = z.infer<typeof reingestResponseSchema>;

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
