import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

// Dedicated proxy, NOT lib/backend-fetch's proxyToBackend — that helper
// hardcodes `content-type: application/json` and reads the body via
// request.text(), which would corrupt a binary .xlsx multipart upload and
// drop the multipart boundary.

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const backendUrl = process.env["BACKEND_PUBLIC_URL"];
  if (!backendUrl) {
    throw new Error("BACKEND_PUBLIC_URL is not set");
  }

  const cookie = request.headers.get("cookie");
  const contentType = request.headers.get("content-type");
  const body = await request.arrayBuffer();

  const backendResponse = await fetch(`${backendUrl}/api/excel/reingest`, {
    method: "POST",
    headers: {
      ...(contentType ? { "content-type": contentType } : {}),
      ...(cookie ? { cookie } : {}),
    },
    body,
  });

  const responseBody = await backendResponse.text();
  return new NextResponse(responseBody, {
    status: backendResponse.status,
    headers: { "content-type": "application/json" },
  });
}
