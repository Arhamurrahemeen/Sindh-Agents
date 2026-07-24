import { describe, expect, it } from "vitest";

import { parseEnv } from "./env";

const validSource = {
  NODE_ENV: "development",
  NEXT_PUBLIC_APP_URL: "http://localhost:3000",
  NEXT_PUBLIC_WIDGET_URL: "http://localhost:3000/widget",
  NEXT_PUBLIC_API_BASE_URL: "http://localhost:3000/api",
  BACKEND_PUBLIC_URL: "http://localhost:8000",
  BETTER_AUTH_SECRET: "secret",
  BETTER_AUTH_URL: "http://localhost:3000",
  FEATURE_PAYMENT_TOGGLE: "false",
  FEATURE_AUDIT_FLAG: "true",
  REQUEST_ID_HEADER: "X-Request-ID",
} as unknown as NodeJS.ProcessEnv;

describe("parseEnv", () => {
  it("parses a valid environment and coerces boolean strings", () => {
    const env = parseEnv(validSource);
    expect(env.FEATURE_PAYMENT_TOGGLE).toBe(false);
    expect(env.FEATURE_AUDIT_FLAG).toBe(true);
  });

  it("throws when a required var is missing", () => {
    const { BETTER_AUTH_SECRET: _drop, ...incomplete } = validSource as Record<
      string,
      string
    >;
    expect(() =>
      parseEnv(incomplete as unknown as NodeJS.ProcessEnv),
    ).toThrow();
  });

  it("throws when a URL var is malformed", () => {
    const bad = { ...validSource, NEXT_PUBLIC_APP_URL: "not-a-url" };
    expect(() => parseEnv(bad as unknown as NodeJS.ProcessEnv)).toThrow();
  });
});
