import type { NextRequest } from "next/server";

import { proxyToBackend } from "@/lib/backend-fetch";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  return proxyToBackend(request, "/api/auth/logout");
}
