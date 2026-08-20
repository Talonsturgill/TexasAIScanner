// scan-progress: the routine's only way to write. It appends one line of the feed, says a run
// has started, or says it has finished, and it can do nothing else.
//
// WHY A FUNCTION RATHER THAN THE SERVICE KEY. The routine is a long-running agent that fetches
// pages a stranger named. Handing it the service role key would hand it the whole database:
// every scan, every address, every request ip. What it holds instead is one append-only secret
// that reaches exactly three RPCs on one row it was already told about. A leak of that secret
// lets somebody write a line onto a scan whose uuid they already know, and read nothing.
//
// NOT PUBLIC, unlike its two siblings. scan-request is a form endpoint and scan-result is
// served by token, so both are open by design. This one is called by the routine and by
// nothing else, so it wants a secret and gets one.
//
// verify_jwt stays OFF for the same reason as the others: the caller is a routine, not an
// account, and the shared secret is the credential.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const env = (k: string, d = "") => Deno.env.get(k) ?? d;
const sb = createClient(env("SUPABASE_URL"), env("SUPABASE_SERVICE_ROLE_KEY"), {
  auth: { persistSession: false },
});

// No CORS. Nothing in a browser calls this, and saying so in the headers is free.
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

// Constant time enough for a shared secret, and it refuses an unset one rather than
// accidentally accepting every caller when the config is missing.
function allowed(req: Request, secret: string): boolean {
  if (!secret) return false;
  const got = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  if (got.length !== secret.length) return false;
  let diff = 0;
  for (let i = 0; i < secret.length; i++) diff |= got.charCodeAt(i) ^ secret.charCodeAt(i);
  return diff === 0;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  const { data: cfg } = await sb.rpc("scanner_config");
  const secret = env("SCAN_PROGRESS_SECRET") ||
    String((cfg ?? {})["progress_secret"] ?? "");
  if (!allowed(req, secret)) return json({ error: "no" }, 401);

  let b: Record<string, unknown>;
  try { b = await req.json(); } catch { return json({ error: "bad json" }, 400); }

  const id = String(b.scan_id ?? "");
  if (!UUID.test(id)) return json({ error: "bad scan_id" }, 400);

  const kind = String(b.kind ?? "line");

  if (kind === "running") {
    const { data } = await sb.rpc("scanner_mark_running", { p_id: id });
    return json(data ?? { ok: false });
  }

  if (kind === "done") {
    const { data } = await sb.rpc("scanner_mark_done", {
      p_id: id,
      p_headline: String(b.headline ?? ""),
      p_html: b.html == null ? null : String(b.html),
      p_scan: b.scan ?? null,
      p_degraded: b.degraded === true,
    });
    return json(data ?? { ok: false });
  }

  const { data } = await sb.rpc("scanner_progress", {
    p_id: id,
    p_phase: String(b.phase ?? ""),
    p_note: String(b.note ?? ""),
  });
  return json(data ?? { ok: false });
});
