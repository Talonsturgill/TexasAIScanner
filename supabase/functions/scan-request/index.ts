// scan-request: the GATEKEEPER. The only thing the public form talks to.
// Validates input, verifies the captcha, enforces per-IP and global daily caps,
// serves a cached scan for a domain seen recently, otherwise creates a scans
// row and fires the Claude routine's API trigger.
//
// IT HOLDS THE TRIGGER SECRET SERVER-SIDE. The browser never sees it and never
// touches the database. That is the whole reason this function exists rather
// than the form calling the routine API directly.
//
// verify_jwt is OFF deliberately: this is a public form endpoint with its own
// authentication story, which is the captcha plus the caps below. A JWT here
// would mean the browser holds a credential, which is the thing being avoided.
//
// All database access goes through the service-role-only RPC API
// (public.scanner_*). The scanner schema is never exposed through PostgREST.
//
// Config resolution: env first, then the scanner.config table (scanner_config
// RPC), then the default. Keys: trigger_url, trigger_secret, turnstile_secret,
// daily_cap, ip_cap, cache_hours, captcha_required. The table lets the whole
// thing be wired with one SQL insert, no redeploy.
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

// The ONE domain normalization rule, matching scripts/normalize_domain.py.
//   https://www.Alamo-Plumbing.com/about  ->  alamo-plumbing.com
function normalizeDomain(raw: string): string {
  if (!raw) return "";
  let s = raw.trim().toLowerCase();
  if (!s) return "";
  if (!s.includes("://")) s = "http://" + s;
  let host: string;
  try {
    host = new URL(s).host;
  } catch {
    return "";
  }
  host = host.split("@").pop()!.split(":")[0];
  if (host.startsWith("www.")) host = host.slice(4);
  return host.replace(/^\.+|\.+$/g, "");
}

const isEmail = (e: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test((e || "").trim());

// FAIL CLOSED. A missing or typo'd secret used to silently disable the captcha,
// which is the exact failure you never notice until you are being drained. The
// only way to run without a captcha is to say so out loud in config
// (captcha_required = "false"), and that is a deliberate, visible choice.
async function turnstileOk(
  secret: string, token: string, ip: string, required: boolean,
): Promise<boolean> {
  if (!secret) {
    if (required) {
      console.error("turnstile secret unset while captcha_required, refusing");
      return false;
    }
    console.warn("turnstile secret unset and captcha_required=false, captcha skipped");
    return true;
  }
  const form = new FormData();
  form.append("secret", secret);
  form.append("response", token || "");
  if (ip) form.append("remoteip", ip);
  const r = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
    method: "POST", body: form,
  });
  const d = await r.json().catch(() => ({ success: false }));
  return !!d.success;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  const ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
  const ua = req.headers.get("user-agent") || "";

  let payload: any;
  try { payload = await req.json(); } catch { return json({ error: "bad json" }, 400); }

  const domain = normalizeDomain(payload.url || "");
  if (!domain || !domain.includes(".")) return json({ error: "give a real website url" }, 400);

  // The requester's OWN optional urls only. We do not fetch anything else.
  const booking_url = typeof payload.booking_url === "string" ? payload.booking_url.slice(0, 500) : null;
  const jobs_signal = typeof payload.jobs === "string" ? payload.jobs.slice(0, 2000) : null;

  // Optional "send me my scan when it is ready". Nothing sends automatically:
  // it rides the row into a human-gated draft.
  const notify_email =
    typeof payload.notify_email === "string" && isEmail(payload.notify_email)
      ? payload.notify_email.trim().slice(0, 320)
      : null;

  const { data: dbCfg } = await sb.rpc("scanner_config");
  const cfg = (k: string, d = "") => env(k.toUpperCase(), "") || (dbCfg?.[k] ?? d);

  const captchaRequired = cfg("captcha_required", "true").toLowerCase() !== "false";
  if (!(await turnstileOk(cfg("turnstile_secret"), payload.turnstile_token || "", ip, captchaRequired))) {
    return json({ error: "captcha failed, try again" }, 403);
  }

  // CAPS. This is the ceiling that stands between a public form and a bill.
  // The global count uses the America/Chicago day.
  const dailyCap = parseInt(cfg("scan_daily_cap", "") || cfg("daily_cap", "25"), 10);
  const ipCap = parseInt(cfg("scan_ip_cap", "") || cfg("ip_cap", "2"), 10);
  const { data: todayN } = await sb.rpc("scanner_today_count");
  if ((todayN ?? 0) >= dailyCap) return json({ error: "we are at capacity today, try tomorrow" }, 429);
  if (ip) {
    const { data: ipN } = await sb.rpc("scanner_ip_count", { p_ip: ip });
    if ((ipN ?? 0) >= ipCap) return json({ error: "you have run several scans, give it a bit" }, 429);
  }

  // Cache. A recent completed scan for this domain returns its token, no new run.
  const cacheHours = parseInt(cfg("cache_hours", "168"), 10);
  const { data: cached } = await sb.rpc("scanner_cached", { p_domain: domain, p_hours: cacheHours });
  if (cached?.token) return json({ token: cached.token, status: cached.status, cached: true });

  const { data: row, error } = await sb.rpc("scanner_create", {
    p_domain: domain, p_booking: booking_url, p_jobs: jobs_signal, p_ip: ip, p_ua: ua,
    p_notify: notify_email,
  });
  if (error || !row?.token) return json({ error: "could not start the scan" }, 500);

  // Fire the routine trigger. Secret stays here, server-side.
  const trigUrl = cfg("scan_routine_trigger_url", "") || cfg("trigger_url", "");
  const trigSecret = cfg("scan_routine_trigger_secret", "") || cfg("trigger_secret", "");
  if (!trigUrl) {
    await sb.rpc("scanner_mark_failed", { p_id: row.id, p_error: "trigger url unset" });
    return json({ error: "scanner not fully configured" }, 500);
  }
  try {
    // The routines fire API (POST .../routines/<id>/fire) requires the beta
    // headers and takes ONE freeform "text" field. The scan pointer rides
    // inside it as JSON. The routine treats it as DATA and never as
    // instructions, and works from the row this gatekeeper wrote.
    const r = await fetch(trigUrl, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "experimental-cc-routine-2026-04-01",
        ...(trigSecret ? { authorization: `Bearer ${trigSecret}` } : {}),
      },
      body: JSON.stringify({
        text: JSON.stringify({ scan_id: row.id, domain, booking_url, jobs_signal }),
      }),
    });
    if (!r.ok) throw new Error(`trigger ${r.status}`);
  } catch (e) {
    await sb.rpc("scanner_mark_failed", { p_id: row.id, p_error: String(e) });
    return json({ error: "could not start the scan, try again shortly" }, 502);
  }

  return json({ token: row.token, status: "queued", cached: false });
});
