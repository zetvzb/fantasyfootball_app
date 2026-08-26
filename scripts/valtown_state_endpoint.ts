// Durable-state endpoint for FANTASYFOOTBALL_STATE_URL, meant to run as a
// Val Town HTTP val (https://val.town). See DEPLOYMENT.md for how the app
// uses this: GET restores the last checkpoint (404 if none saved yet), PUT
// checkpoints the current state. Both are plain HTTP -- the app never uses
// any provider-specific signing, just an optional bearer token and an
// ETag/If-Match pair for optimistic-concurrency conflict detection.
//
// Setup:
//   1. Create a free account at https://www.val.town (GitHub sign-in is
//      fastest).
//   2. Create a new val, choose the HTTP trigger, and paste this file's
//      contents in as its code.
//   3. In the val's environment variables (left sidebar), add STATE_TOKEN
//      set to a random secret you generate yourself, e.g. via
//      `openssl rand -hex 32` in a terminal. This is required -- without
//      it, anyone who finds the val's URL could read or overwrite your
//      league data.
//   4. Copy the val's public URL (shown at the top of the val page, looks
//      like https://<you>-<valname>.web.val.run) into the deployed app's
//      FANTASYFOOTBALL_STATE_URL environment variable, and the same
//      STATE_TOKEN value into FANTASYFOOTBALL_STATE_TOKEN.
//   5. Test locally before trusting it for a live draft: set both env vars
//      in your shell, run the app, make a change on League Setup, restart
//      the app, and confirm the change is still there.

const KEY = "fantasyfootball-state.zip";

async function sha256Hex(data: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

async function readExistingEtag(
  blob: { get(key: string): Promise<Response> },
): Promise<string | null> {
  try {
    const existing = await blob.get(KEY);
    const body = await existing.arrayBuffer();
    return await sha256Hex(body);
  } catch {
    return null;
  }
}

export default async function (req: Request): Promise<Response> {
  const { blob } = await import("https://esm.town/v/std/blob/main.ts");

  const expectedToken = Deno.env.get("STATE_TOKEN");
  if (expectedToken) {
    const provided = req.headers.get("Authorization") || "";
    if (provided !== `Bearer ${expectedToken}`) {
      return new Response("Unauthorized", { status: 401 });
    }
  }

  if (req.method === "GET") {
    let stored: Response;
    try {
      stored = await blob.get(KEY);
    } catch {
      return new Response("Not Found", { status: 404 });
    }
    const body = await stored.arrayBuffer();
    if (!body.byteLength) {
      return new Response("Not Found", { status: 404 });
    }
    const etag = await sha256Hex(body);
    return new Response(body, {
      status: 200,
      headers: { "ETag": etag, "Content-Type": "application/zip" },
    });
  }

  if (req.method === "PUT") {
    const body = await req.arrayBuffer();
    const ifMatch = req.headers.get("If-Match");
    if (ifMatch) {
      const currentEtag = await readExistingEtag(blob);
      if (currentEtag !== ifMatch) {
        return new Response("Precondition Failed", { status: 412 });
      }
    }
    await blob.set(KEY, body);
    const newEtag = await sha256Hex(body);
    return new Response(null, { status: 200, headers: { "ETag": newEtag } });
  }

  return new Response("Method Not Allowed", { status: 405 });
}
