import { NextRequest, NextResponse } from "next/server";

// Server-only — do not import from a 'use client' file. Route handlers proxy
// browser requests to FastAPI (api-contract.md §0.1/§0.11: the browser only
// ever talks to Next's own /api/*, same-origin; this is the other half).

export async function fetchBackend(
  path: string,
  cookieHeader?: string,
): Promise<Response> {
  const backendUrl = process.env["BACKEND_PUBLIC_URL"];
  if (!backendUrl) {
    throw new Error("BACKEND_PUBLIC_URL is not set");
  }
  return fetch(`${backendUrl}${path}`, {
    headers: cookieHeader ? { cookie: cookieHeader } : {},
    cache: "no-store",
  });
}

export async function proxyToBackend(
  request: NextRequest,
  backendPath: string,
): Promise<NextResponse> {
  const backendUrl = process.env["BACKEND_PUBLIC_URL"];
  if (!backendUrl) {
    throw new Error("BACKEND_PUBLIC_URL is not set");
  }

  const cookie = request.headers.get("cookie");
  const idempotencyKey = request.headers.get("idempotency-key");
  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const query = request.nextUrl.search;

  const backendResponse = await fetch(`${backendUrl}${backendPath}${query}`, {
    method: request.method,
    headers: {
      "content-type": "application/json",
      ...(cookie ? { cookie } : {}),
      ...(idempotencyKey ? { "idempotency-key": idempotencyKey } : {}),
    },
    ...(hasBody ? { body: await request.text() } : {}),
  });

  const responseBody = await backendResponse.text();
  const response = new NextResponse(responseBody, {
    status: backendResponse.status,
    headers: { "content-type": "application/json" },
  });

  for (const setCookie of backendResponse.headers.getSetCookie()) {
    response.headers.append("set-cookie", setCookie);
  }

  return response;
}
