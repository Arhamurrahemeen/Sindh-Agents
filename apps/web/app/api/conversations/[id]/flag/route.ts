import type { NextRequest } from "next/server";

import { proxyToBackend } from "@/lib/backend-fetch";

export const dynamic = "force-dynamic";

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } },
) {
  return proxyToBackend(request, `/api/conversations/${params.id}/flag`);
}
