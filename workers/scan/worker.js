// The scan flow behind texasaidocket.com/scan/. Four routes, one worker, one D1 binding.
//
// WHAT THIS REPLACED AND WHY. Until 2026-08-20 this was a Supabase project: Postgres with RLS
// and eight service-role functions, three Deno edge functions in front of them, and a service
// role key. The owner's call was that it was a flaky second vendor, and the argument for moving
// was already written in this project, in the ask box's own worker: Cloudflare already serves
// the domain and Turnstile, so this adds a file rather than a vendor.
//
// THE SECURITY MODEL DID NOT WEAKEN IN THE MOVE, and it is worth being precise about why,
// because "we deleted the database" is the kind of sentence that usually means it did.
// Postgres protected the table with RLS-with-no-policies plus service-role-only functions, so
// the anon key saw nothing. Here there is no anon key and no query endpoint: nothing but this
// worker holds a binding to the database, db.js is the entire set of questions anyone can ask
// it, and every one of them is a literal statement with bound parameters.
//
//   POST /request   the GATEKEEPER, and the only route the public form talks to. It holds the
//                   trigger secret server-side, which is the whole reason it exists rather than
//                   the form calling the routine API directly.
//   POST /result    one scan by its unguessable token. Open by design: the token IS the
//                   credential, and a JWT here would mean issuing an account to somebody who
//                   filled in a form once.
//   POST /progress  the routine's ONLY way to write. Secret, and no CORS at all, because
//                   nothing in a browser calls it.
//   POST /notify    set the delivery address, once, never overwritten.

import {
  appendLine, cached, chicagoDayStart, create, getByToken, isEmail, markDone, markFailed,
  markRunning, normalizeDomain, setNotify, todayCount, ipCount,
} from "./db.js";

const DEFAULT_ORIGIN = "https://texasaidocket.com";
// THE DOMAIN WINDOW IS THIRTY DAYS, WHICH IS WHAT THE DOCS ALWAYS SAID IT WAS.
// It sat at 168 hours, seven days, while CLAUDE.md and the run contract both promised that a
// domain is not rescanned inside thirty. The gap was paid for in real money: a domain scanned
// on the 1st could fire a whole second routine run on the 9th and nothing refused it.
//
// This is the check that actually prevents the spend, because it runs BEFORE the routine is
// fired. The ledger check inside the routine runs after the container is already up.
// The two behave differently on purpose and that is not drift. This one SERVES THE EARLIER
// REPORT, which is a better answer for the requester than a refusal. The routine's own check
// REFUSES, because by the time it runs there is nothing cached to hand back.
const DEFAULTS = { daily_cap: 25, ip_cap: 2, cache_hours: 720 };

// Read from the environment rather than hardcoded, the same lesson the ask worker learned when
// the site moved off a github.io subpath and a hardcoded origin would have needed a redeploy.
const corsFor = (env) => ({
  "access-control-allow-origin": env.SCAN_ORIGIN || DEFAULT_ORIGIN,
  "access-control-allow-methods": "POST, OPTIONS",
  "access-control-allow-headers": "content-type",
  "access-control-max-age": "86400",
});

const json = (body, status, headers = {}) =>
  new Response(JSON.stringify(body), {
    status, headers: { "content-type": "application/json", ...headers },
  });

const num = (v, d) => {
  const n = parseInt(v, 10);
  return Number.isFinite(n) && n >= 0 ? n : d;
};

// FAIL CLOSED. A missing or mistyped secret used to silently disable the captcha, which is the
// exact failure nobody notices until they are being drained. The only way to run without one is
// to say so out loud in the environment, and that is a deliberate, visible choice.
export async function turnstileOk(secret, token, ip, required) {
  if (!secret) {
    // Says which of the two silences this is, because they need different fixes and the
    // requester sees the same sentence either way.
    console.warn(required
      ? "turnstile: TURNSTILE_SECRET is unset and the captcha is required, so every request is refused"
      : "turnstile: TURNSTILE_SECRET is unset and CAPTCHA_REQUIRED is false, so the captcha is skipped");
    return !required;
  }
  const form = new FormData();
  form.append("secret", secret);
  form.append("response", token || "");
  if (ip) form.append("remoteip", ip);
  const r = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify",
    { method: "POST", body: form });
  const d = await r.json().catch(() => ({ success: false }));
  if (d.success === true) return true;

  // WHY THE CODES ARE LOGGED. Cloudflare tells you exactly which of four different things went
  // wrong, and this used to throw all of it away and say "captcha failed" to everybody. A
  // widget that says Success on the page and a server that refuses it is the same sentence
  // whether the secret is missing, belongs to another widget, or the token was already spent,
  // and those need three different fixes. An hour went into guessing between them.
  //
  //   missing-input-secret     nothing is set
  //   invalid-input-secret     set, but not the secret paired with the site key on the page
  //   invalid-input-response   the token is malformed
  //   timeout-or-duplicate     the token was already used, or is older than five minutes
  //
  // LOGGED, NEVER RETURNED. A stranger at a public form learns nothing about how this is
  // configured; the operator reads it in the live log stream.
  const codes = Array.isArray(d["error-codes"]) ? d["error-codes"] : [];
  console.warn("turnstile refused: " + (codes.join(", ") || "no error code given"));
  return false;
}

// Constant time for a shared secret, and it refuses an unset one rather than accidentally
// accepting every caller the day somebody forgets to set it.
export function secretOk(request, secret) {
  if (!secret) return false;
  const got = (request.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  if (got.length !== secret.length) return false;
  let diff = 0;
  for (let i = 0; i < secret.length; i++) diff |= got.charCodeAt(i) ^ secret.charCodeAt(i);
  return diff === 0;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// ------------------------------------------------------------------------------- /request

export async function handleRequest(request, env, nowMs) {
  const db = env.SCAN_DB;
  const cors = corsFor(env);
  const now = Math.floor(nowMs / 1000);
  const ip = request.headers.get("cf-connecting-ip")
    || (request.headers.get("x-forwarded-for") || "").split(",")[0].trim();
  const ua = request.headers.get("user-agent") || "";

  let p;
  try { p = await request.json(); } catch { return json({ error: "bad json" }, 400, cors); }

  const domain = normalizeDomain(p.url || "");
  if (!domain || !domain.includes(".")) {
    return json({ error: "give a real website url" }, 400, cors);
  }

  // The requester's OWN optional urls only. Nothing else is ever fetched on their say-so.
  const booking_url = typeof p.booking_url === "string" ? p.booking_url : null;
  const jobs_signal = typeof p.jobs === "string" ? p.jobs : null;
  const notify_email = isEmail(p.notify_email) ? String(p.notify_email).trim() : null;

  // The form's free-text box. Stored so a PERSON can read it, and never put in the trigger
  // payload below, so it cannot reach an agent as instructions.
  const note = typeof p.note === "string" ? p.note : null;

  const captchaRequired = String(env.CAPTCHA_REQUIRED ?? "true").toLowerCase() !== "false";
  if (!(await turnstileOk(env.TURNSTILE_SECRET, p.turnstile_token || "", ip, captchaRequired))) {
    return json({ error: "captcha failed, try again" }, 403, cors);
  }

  // CAPS. The ceiling that stands between a public form and a bill. The global one counts the
  // Texas day, not the UTC one.
  const dayStart = chicagoDayStart(nowMs);
  if (await todayCount(db, dayStart) >= num(env.DAILY_CAP, DEFAULTS.daily_cap)) {
    return json({ error: "we are at capacity today, try tomorrow" }, 429, cors);
  }
  if (ip && await ipCount(db, ip, now - 86400) >= num(env.IP_CAP, DEFAULTS.ip_cap)) {
    return json({ error: "you have run several scans, give it a bit" }, 429, cors);
  }

  const hours = num(env.CACHE_HOURS, DEFAULTS.cache_hours);
  const hit = await cached(db, domain, now - hours * 3600);
  if (hit) return json({ token: hit.token, status: hit.status, cached: true }, 200, cors);

  let row;
  try {
    row = await create(db, {
      domain, booking_url, jobs_signal, notify_email, note, request_ip: ip, user_agent: ua,
    }, now);
  } catch {
    return json({ error: "could not start the scan" }, 500, cors);
  }

  if (!env.TRIGGER_URL) {
    await markFailed(db, row.id, "trigger url unset", now);
    return json({ error: "scanner not fully configured" }, 500, cors);
  }
  try {
    // The routines fire API takes ONE freeform "text" field. The scan pointer rides inside it
    // as JSON, and the routine treats it as DATA and never as instructions: it works from the
    // row this gatekeeper wrote, which is why the free text is not in here.
    const r = await fetch(env.TRIGGER_URL, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "experimental-cc-routine-2026-04-01",
        ...(env.TRIGGER_SECRET ? { authorization: `Bearer ${env.TRIGGER_SECRET}` } : {}),
      },
      body: JSON.stringify({
        text: JSON.stringify({ scan_id: row.id, domain, booking_url, jobs_signal }),
      }),
    });
    if (!r.ok) throw new Error(`trigger ${r.status}`);
  } catch (e) {
    await markFailed(db, row.id, String(e), now);
    return json({ error: "could not start the scan, try again shortly" }, 502, cors);
  }

  return json({ token: row.token, status: "queued", cached: false }, 200, cors);
}

// -------------------------------------------------------------------------------- /result

export async function handleResult(request, env, nowMs) {
  const cors = corsFor(env);
  const b = await request.json().catch(() => ({}));
  const token = String(b.token || "");
  // A short token is a guess, not a typo. Refuse before touching the database.
  if (token.length < 8) return json({ error: "bad token" }, 400, cors);
  const out = await getByToken(env.SCAN_DB, token);
  if (!out) return json({ error: "not found" }, 404, cors);
  return json(out, 200, cors);
}

// ------------------------------------------------------------------------------ /progress

// WHY A SECRET AND NOT THE DATABASE. The routine is a long-running agent that fetches pages a
// stranger named. A binding would hand it every scan, every address and every request ip. What
// it holds instead reaches three operations on one row it was already told about, so a leak of
// it lets somebody write a line onto a scan whose uuid they already know, and read nothing.
export async function handleProgress(request, env, nowMs) {
  if (!secretOk(request, env.PROGRESS_SECRET)) return json({ error: "no" }, 401);
  const now = Math.floor(nowMs / 1000);
  const b = await request.json().catch(() => ({}));
  const id = String(b.scan_id || "");
  if (!UUID.test(id)) return json({ error: "bad scan_id" }, 400);

  const kind = String(b.kind || "line");
  if (kind === "running") return json(await markRunning(env.SCAN_DB, id, now));
  if (kind === "done") {
    return json(await markDone(env.SCAN_DB, id, String(b.status || "done"), b.headline,
                               b.html, b.run_ms, now));
  }
  if (kind !== "line") return json({ error: "unknown kind" }, 400);
  const note = String(b.note || "").trim();
  if (!note) return json({ ok: false, error: "empty note" }, 400);
  return json(await appendLine(env.SCAN_DB, id, String(b.phase || ""), note, now));
}

// -------------------------------------------------------------------------------- /notify

export async function handleNotify(request, env, nowMs) {
  const cors = corsFor(env);
  const b = await request.json().catch(() => ({}));
  const token = String(b.token || "");
  if (token.length < 8) return json({ error: "bad token" }, 400, cors);
  if (!isEmail(b.email)) return json({ error: "give a real address" }, 400, cors);
  return json(await setNotify(env.SCAN_DB, token, String(b.email).trim(),
                              Math.floor(nowMs / 1000)), 200, cors);
}

// ----------------------------------------------------------------------------------- door

export const ROUTES = {
  "/request": handleRequest,
  "/result": handleResult,
  "/progress": handleProgress,
  "/notify": handleNotify,
};

export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname.replace(/\/+$/, "") || "/";

    // /progress is not a browser route and gets no CORS headers, which is a statement as much
    // as a control: nothing in a page should ever be able to write to a feed.
    if (request.method === "OPTIONS") {
      if (path === "/progress") return new Response("no", { status: 405 });
      return new Response(null, { status: 204, headers: corsFor(env) });
    }

    const handler = ROUTES[path];
    if (!handler) return json({ error: "not found" }, 404);
    if (request.method !== "POST") return json({ error: "POST only" }, 405);
    if (!env.SCAN_DB) return json({ error: "scanner not configured" }, 503);

    try {
      return await handler(request, env, Date.now());
    } catch (e) {
      console.error(path, String(e));
      return json({ error: "something went wrong" }, 500,
                  path === "/progress" ? {} : corsFor(env));
    }
  },
};
