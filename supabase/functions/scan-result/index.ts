// scan-result: read exactly ONE scan by its unguessable public_token and return
// the safe shape. Nothing else is reachable from the browser.
//
// The read goes through the service-role-only RPC (public.scanner_get_by_token),
// which returns status, headline, the progress feed, and the html only once the
// scan is finished. The scanner schema is never exposed through PostgREST, so
// there is no query a caller can widen: the token gets one row or nothing.
//
// verify_jwt is OFF deliberately. The token IS the credential, it is 128 bits of
// gen_random_bytes, and it is what the requester was handed. A JWT here would
// mean issuing an account to somebody who filled in a form once.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const env = (k: string, d = "") => Deno.env.get(k) ?? d;
const sb = createClient(env("SUPABASE_URL"), env("SUPABASE_SERVICE_ROLE_KEY"), {
  auth: { persistSession: false },
});

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
};

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, "content-type": "application/json" },
  });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });

  const url = new URL(req.url);
  let token = url.searchParams.get("token") || "";
  if (req.method === "POST" && !token) {
    const b = await req.json().catch(() => ({}));
    token = b.token || "";
  }
  // A short token is a guess, not a typo. Refuse before touching the database.
  if (!token || token.length < 8) return json({ error: "bad token" }, 400);

  const { data, error } = await sb.rpc("scanner_get_by_token", { p_token: token });
  if (error) return json({ error: "lookup failed" }, 500);
  if (!data) return json({ error: "not found" }, 404);

  return json(data);
});
