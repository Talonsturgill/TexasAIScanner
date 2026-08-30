// GENERATED FILE. Do not edit.
//
// The scan worker's two modules flattened into one, so it can be deployed by pasting into
// the Cloudflare dashboard without a terminal. Regenerate with:
//
//   node workers/scan/bundle.mjs
//
// Edit db.js or worker.js instead. The tests run against those, and
// the bundle is checked to hold every one of them, so the two can't drift silently.

// ==========================================================================
// db.js
// ==========================================================================

// The scan record, and every question anyone is allowed to ask it.
//
// This is the whole data surface. It replaced eight service-role-only Postgres functions on
// 2026-08-20, and the shape was kept deliberately narrow for the same reason they were: the
// worker in front of this is a public form endpoint, so the set of things reachable through it
// should be a list somebody can read in one sitting rather than a query language.
//
// NOTHING HERE TAKES A TABLE NAME OR A COLUMN LIST FROM A CALLER. Every statement below is a
// literal with bound parameters. That is not a style preference: the previous design leaned on
// PostgREST never exposing the schema, and the equivalent protection here is that there is no
// generic query path at all.

export const FEED_CAP = 600;   // lines, and it refuses rather than dropping. See appendLine.
export const NOTE_MAX = 300;   // characters of one line
export const PHASE_MAX = 40;

const FINISHED = ["done", "degraded", "failed"];

// ---------------------------------------------------------------------------- pure helpers

// THE ONE DOMAIN NORMALIZATION RULE, matching scripts/normalize_domain.py character for
// character. Two implementations of this exist on purpose, one at the door and one in the
// routine, and they have to agree or a cached scan is never found for a domain that was
// already scanned.
//   https://www.Alamo-Plumbing.com/about  ->  alamo-plumbing.com
export function normalizeDomain(raw) {
  if (!raw) return "";
  let s = String(raw).trim().toLowerCase();
  if (!s) return "";
  if (!s.includes("://")) s = "http://" + s;
  let host;
  try { host = new URL(s).host; } catch { return ""; }
  host = host.split("@").pop().split(":")[0];
  if (host.startsWith("www.")) host = host.slice(4);
  return host.replace(/^\.+|\.+$/g, "");
}

export const isEmail = (e) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(e || "").trim());

// THE TEXAS DAY, computed from the zone database rather than from a fixed offset. The daily cap
// is the ceiling between a public form and a bill, and a hardcoded -6 is wrong for half the
// year: the cap would reset an hour early every summer and nobody would notice, because a cap
// resetting early looks exactly like a quiet day.
export function chicagoDayStart(nowMs) {
  const f = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Chicago", hour: "2-digit", minute: "2-digit", second: "2-digit",
    hour12: false,
  });
  const p = {};
  for (const { type, value } of f.formatToParts(nowMs)) p[type] = value;
  const into = (Number(p.hour) % 24) * 3600 + Number(p.minute) * 60 + Number(p.second);
  return Math.floor(nowMs / 1000) - into;
}

// 128 bits, the same width the Postgres default used, and from the platform CSPRNG. This is the
// entire credential a requester holds: no account, no cookie, no second factor. It is why the
// read path can be open and still only ever serve one person's scan.
export function newToken() {
  const b = new Uint8Array(16);
  crypto.getRandomValues(b);
  return [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
}

const clip = (s, n) => (s == null ? null : String(s).slice(0, n));

// ---------------------------------------------------------------------------- reads

export async function todayCount(db, sinceEpoch) {
  const r = await db.prepare("select count(*) as n from scans where created_at >= ?")
    .bind(sinceEpoch).first();
  return r ? Number(r.n) : 0;
}

export async function ipCount(db, ip, sinceEpoch) {
  if (!ip) return 0;
  const r = await db.prepare(
    "select count(*) as n from scans where request_ip = ? and created_at >= ?")
    .bind(ip, sinceEpoch).first();
  return r ? Number(r.n) : 0;
}

// A recent FINISHED scan for this domain, so a second person asking about the same business
// gets the answer instead of a second bill.
export async function cached(db, domain, sinceEpoch) {
  const r = await db.prepare(
    "select public_token, status from scans " +
    "where domain = ? and status in ('done','degraded') and created_at >= ? " +
    "order by created_at desc limit 1")
    .bind(domain, sinceEpoch).first();
  return r ? { token: r.public_token, status: r.status } : null;
}

// ONE SCAN, BY ITS TOKEN, IN THE SAFE SHAPE. The html comes back only once the scan is
// finished; the feed comes back always, so the requester can watch. The columns not named here
// are the reason this is a function and not a select star: request_ip, user_agent, note and
// notify_email exist on the row and never leave it.
export async function getByToken(db, token) {
  const r = await db.prepare(
    "select status, headline, progress, result_html from scans where public_token = ?")
    .bind(token).first();
  if (!r) return null;
  let progress = [];
  try { progress = JSON.parse(r.progress || "[]"); } catch { progress = []; }
  return {
    status: r.status,
    headline: r.headline ?? null,
    progress: Array.isArray(progress) ? progress : [],
    html: (r.status === "done" || r.status === "degraded") ? (r.result_html ?? null) : null,
  };
}

// ---------------------------------------------------------------------------- writes

export async function create(db, f, nowEpoch) {
  const id = crypto.randomUUID();
  const token = newToken();
  await db.prepare(
    "insert into scans (id, created_at, updated_at, domain, status, public_token, " +
    "booking_url, jobs_signal, notify_email, note, request_ip, user_agent) " +
    "values (?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?)")
    .bind(id, nowEpoch, nowEpoch, f.domain, token, clip(f.booking_url, 500),
          clip(f.jobs_signal, 2000), clip(f.notify_email, 320), clip(f.note, 4000),
          f.request_ip || null, clip(f.user_agent, 500))
    .run();
  return { id, token };
}

export async function markFailed(db, id, error, nowEpoch) {
  await db.prepare("update scans set status='failed', error=?, updated_at=? where id=?")
    .bind(clip(error, 500), nowEpoch, id).run();
}

// The run has started. Separate from the first progress line because a scan can be picked up
// and say nothing for a while, and "queued" and "running" are different things to somebody
// watching a page.
export async function markRunning(db, id, nowEpoch) {
  const r = await db.prepare(
    "update scans set status='running', updated_at=? where id=? and status='queued'")
    .bind(nowEpoch, id).run();
  return changed(r) ? { ok: true } : { ok: false, error: "not queued" };
}

// WRITE ONCE. A verdict that can be rewritten is not a verdict, and a late line from a run that
// already finished must not be able to reopen one.
export async function markDone(db, id, status, headline, html, runMs, nowEpoch) {
  const st = FINISHED.includes(status) ? status : "done";
  const r = await db.prepare(
    "update scans set status=?, headline=?, result_html=?, run_ms=?, updated_at=? " +
    "where id=? and status not in ('done','degraded','failed')")
    .bind(st, clip(headline, 300), html ?? null, Number.isFinite(runMs) ? runMs : null,
          nowEpoch, id)
    .run();
  return changed(r) ? { ok: true } : { ok: false, error: "already finished" };
}

// ONE LINE OF THE FEED, APPENDED, bounded three ways because this row is served to a stranger's
// browser and is written by a long-running agent:
//
//   the note is TRIMMED, so one runaway line cannot become the page
//   the feed is CAPPED, and it REFUSES rather than dropping the oldest line, because the watch
//     page reads by index and a shifting array would move a line under a reader mid sentence
//   a finished scan REFUSES more, so the story cannot change after it has been told
//
// The cap is set for DEPTH, not for a summary. A scan that reads twenty pages and rules out
// thirty published results should be able to say so line by line. Six hundred is roughly an
// order of magnitude above a thorough run: it stops a loop, it does not ration the reporting.
export async function appendLine(db, id, phase, note, nowEpoch) {
  const row = await db.prepare("select status, progress from scans where id = ?")
    .bind(id).first();
  if (!row) return { ok: false, error: "no such scan" };
  if (FINISHED.includes(row.status)) return { ok: false, error: "scan is finished" };

  let feed = [];
  try { feed = JSON.parse(row.progress || "[]"); } catch { feed = []; }
  if (!Array.isArray(feed)) feed = [];
  if (feed.length >= FEED_CAP) return { ok: false, error: "feed is full" };

  feed.push({
    at: new Date(nowEpoch * 1000).toISOString().replace(/\.\d+Z$/, "Z"),
    phase: clip(phase || "", PHASE_MAX),
    note: clip(note || "", NOTE_MAX),
  });

  // Guarded on the length it was read at, so two lines racing cannot both write and lose one.
  // D1 gives no transaction across a read and a write, and this is what that costs: on a
  // collision the second append fails and the routine, which treats every feed call as
  // best effort, carries on. A dropped courtesy line is the right thing to lose here.
  const r = await db.prepare(
    "update scans set progress=?, status=case when status='queued' then 'running' else status " +
    "end, updated_at=? where id=? and json_array_length(progress)=?")
    .bind(JSON.stringify(feed), nowEpoch, id, feed.length - 1).run();
  return changed(r) ? { ok: true } : { ok: false, error: "raced, line dropped" };
}

// SET ONCE. A scan link is shareable, so an address already on the row is never overwritten:
// otherwise a shared link could redirect somebody else's delivery, or be used to mail a
// stranger who never asked for anything.
export async function setNotify(db, token, email, nowEpoch) {
  const row = await db.prepare("select id, status, notify_email from scans where public_token=?")
    .bind(token).first();
  if (!row) return { found: false };
  if (row.notify_email) return { found: true, already_set: true, status: row.status };
  await db.prepare("update scans set notify_email=?, updated_at=? where id=?")
    .bind(clip(email, 320), nowEpoch, row.id).run();
  return { found: true, already_set: false, status: row.status };
}

// D1 reports rows written in meta. Read through one helper so a shape change is one edit and
// not a silent "nothing was updated, so the caller thinks it worked".
function changed(r) {
  const n = r && r.meta ? (r.meta.changes ?? r.meta.rows_written) : undefined;
  return typeof n === "number" ? n > 0 : true;
}

// ==========================================================================
// worker.js
// ==========================================================================

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
        // The private routine needs the address to build the one Gmail draft the requester
        // asked for. It never enters an agent prompt or the public result shape. The stranger's
        // free text remains on the D1 row for the maintainer and does not ride this payload.
        text: JSON.stringify({
          scan_id: row.id, domain, booking_url, jobs_signal, notify_email,
        }),
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
