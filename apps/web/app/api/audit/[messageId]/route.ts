import type { NextRequest } from "next/server";

import { proxyToBackend } from "@/lib/backend-fetch";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  { params }: { params: { messageId: string } },
) {
  return proxyToBackend(request, `/api/audit/${params.messageId}`);
}
