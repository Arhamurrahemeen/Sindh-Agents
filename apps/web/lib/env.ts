import { z } from "zod";

const booleanString = z.enum(["true", "false"]).transform((v) => v === "true");

const envSchema = z.object({
  NODE_ENV: z.enum(["development", "staging", "production"]),
  NEXT_PUBLIC_APP_URL: z.string().url(),
  NEXT_PUBLIC_WIDGET_URL: z.string().url(),
  NEXT_PUBLIC_API_BASE_URL: z.string().url(),
  BACKEND_PUBLIC_URL: z.string().url(),
  BETTER_AUTH_SECRET: z.string().min(1),
  BETTER_AUTH_URL: z.string().url(),
  FEATURE_PAYMENT_TOGGLE: booleanString,
  FEATURE_AUDIT_FLAG: booleanString,
  REQUEST_ID_HEADER: z.string().min(1),
});

export type Env = z.infer<typeof envSchema>;

export function parseEnv(source: NodeJS.ProcessEnv): Env {
  const result = envSchema.safeParse(source);
  if (!result.success) {
    throw new Error(
      `Invalid environment configuration: ${result.error.message}`,
    );
  }
  return result.data;
}
