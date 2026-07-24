import type { Metadata } from "next";
import { PHASE_PRODUCTION_BUILD } from "next/constants";

import { parseEnv } from "@/lib/env";

import "./globals.css";

// env_setup.md §0 — fail fast on missing/malformed env at server startup,
// not at first use deep in some component. Skipped during `next build` —
// secrets aren't expected to be present at build time (e.g. Docker images
// built without .env baked in), only when the server actually starts.
if (process.env["NEXT_PHASE"] !== PHASE_PRODUCTION_BUILD) {
  parseEnv(process.env);
}

export const metadata: Metadata = {
  title: "Sindh Agents",
  description: "WhatsApp-first AI employee for Pakistani SMEs",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
