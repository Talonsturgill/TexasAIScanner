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
