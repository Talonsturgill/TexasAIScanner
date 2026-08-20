// The scan worker, against a REAL SQLite loaded from the REAL schema file.
//
// WHY NOT A FAKE DATABASE. A hand written stub proves the code calls the functions the stub
// implements, which is a tautology. Every interesting thing here lives in the storage: whether
// the schema parses at all, whether `json_array_length` sees the feed, whether the unique index
// on the token holds, whether an update guarded on a row's current state actually declines. A
// stub answers none of those and would have shipped a schema that does not apply.
//
// node:sqlite is the same engine D1 runs, wrapped below in the shape D1 presents. What this
// still does NOT prove is the binding, the secrets and the routes as Cloudflare wires them, and
// that is stated rather than papered over: the first real request is the first test of those.
//
// Run: node workers/scan/test.js

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { DatabaseSync } from "node:sqlite";

import {
  appendLine, cached, chicagoDayStart, create, FEED_CAP, getByToken, ipCount, isEmail, markDone,
  markFailed, markRunning, newToken, normalizeDomain, setNotify, todayCount,
} from "./db.js";
import worker, { handleProgress, handleRequest, handleResult, secretOk } from "./worker.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const SCHEMA = join(HERE, "..", "..", "db", "d1_schema.sql");

let fail = 0, pass = 0;
const ok = (label, cond, detail = "") => {
  if (cond) { pass++; return; }
  fail++;
  console.log(`  FAIL  ${label}${detail ? "  " + detail : ""}`);
};
const head = (t) => console.log("\n" + t);

// D1's surface, over the same engine D1 runs.
function d1() {
  const sql = new DatabaseSync(":memory:");
  sql.exec(readFileSync(SCHEMA, "utf8"));
  return {
    prepare(text) {
      const stmt = sql.prepare(text);
      let args = [];
      const api = {
        bind(...a) { args = a; return api; },
        async first() { return stmt.get(...args) ?? null; },
        async run() { const r = stmt.run(...args); return { meta: { changes: r.changes } }; },
        async all() { return { results: stmt.all(...args) }; },
      };
      return api;
    },
  };
}

const req = (body, headers = {}) => new Request("https://x/request", {
  method: "POST", headers: { "content-type": "application/json", ...headers },
  body: JSON.stringify(body),
});

const NOW = Date.UTC(2026, 7, 20, 18, 0, 0);   // a fixed clock, so nothing here is flaky
const sec = Math.floor(NOW / 1000);

// ------------------------------------------------------------------ A. the schema applies
head("A. the schema is real and it applies");
{
  let applied = true, why = "";
  try { d1(); } catch (e) { applied = false; why = String(e); }
  ok("db/d1_schema.sql parses and creates its table", applied, why);
  const db = d1();
  const r = await db.prepare("select count(*) as n from scans").bind().first();
  ok("...and the table starts empty", r.n === 0);
}

// -------------------------------------------------------------------- B. the pure helpers
head("B. the pure helpers, which two implementations have to agree on");
ok("a url is reduced to its bare host",
  normalizeDomain("https://www.Alamo-Plumbing.com/about") === "alamo-plumbing.com",
  normalizeDomain("https://www.Alamo-Plumbing.com/about"));
ok("a bare host survives", normalizeDomain("example.com") === "example.com");
ok("a port and a userinfo are stripped",
  normalizeDomain("http://bob@Example.com:8443/x") === "example.com",
  normalizeDomain("http://bob@Example.com:8443/x"));
ok("nonsense normalizes to nothing", normalizeDomain("   ") === "");
ok("an address is checked shallowly and on purpose", isEmail("a@b.co") && !isEmail("a@b"));
ok("a token is 128 bits of hex", /^[0-9a-f]{32}$/.test(newToken()));
ok("...and two of them differ", newToken() !== newToken());
{
  // The Texas day, in August, is CDT: UTC-5. 18:00Z is 13:00 local, so the day started 13
  // hours ago. This is the check that would have caught a hardcoded offset.
  const start = chicagoDayStart(NOW);
  ok("the daily window starts at midnight in Texas, not in UTC",
    sec - start === 13 * 3600, String((sec - start) / 3600) + "h");
  const winter = Date.UTC(2026, 0, 20, 18, 0, 0);   // CST: UTC-6, so 12:00 local
  ok("...and it follows the zone across daylight saving, rather than a fixed offset",
    Math.floor(winter / 1000) - chicagoDayStart(winter) === 12 * 3600);
}

// ------------------------------------------------------------------------ C. the safe shape
head("C. one scan, by its token, and only the safe fields");
{
  const db = d1();
  const { id, token } = await create(db, {
    domain: "example.com", note: "call me on tuesday", notify_email: "a@b.co",
    request_ip: "203.0.113.9", user_agent: "curl",
  }, sec);
  const out = await getByToken(db, token);
  ok("the row comes back by its token", out !== null);
  ok("...with exactly four fields and no more",
    JSON.stringify(Object.keys(out).sort()) === '["headline","html","progress","status"]',
    JSON.stringify(Object.keys(out)));
  ok("the free text never leaves the row", !JSON.stringify(out).includes("tuesday"));
  ok("the address never leaves the row", !JSON.stringify(out).includes("a@b.co"));
  ok("the request ip never leaves the row", !JSON.stringify(out).includes("203.0.113"));
  ok("a wrong token gets nothing", (await getByToken(db, "deadbeef".repeat(4))) === null);
  ok("the feed starts empty and is an array", Array.isArray(out.progress) && !out.progress.length);
  ok("the html is withheld while it runs", out.html === null);

  await markDone(db, id, "done", "A headline", "<p>the report</p>", 1234, sec);
  const fin = await getByToken(db, token);
  ok("...and served once it has finished", fin.html === "<p>the report</p>");
  ok("the headline comes with it", fin.headline === "A headline");
}

// ------------------------------------------------------------------------- D. the feed
head("D. the feed: trimmed, capped, and closed when the story is told");
{
  const db = d1();
  const { id, token } = await create(db, { domain: "example.com" }, sec);

  ok("a line lands", (await appendLine(db, id, "footprint", "Reading the homepage", sec)).ok);
  const one = await getByToken(db, token);
  ok("...and reads back with its phase and note",
    one.progress[0].phase === "footprint" && one.progress[0].note === "Reading the homepage",
    JSON.stringify(one.progress[0]));
  ok("...and carries a timestamp", /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(one.progress[0].at),
    one.progress[0].at);
  ok("a first line also moves a queued scan to running", one.status === "running");

  const long = "x".repeat(900);
  await appendLine(db, id, "industry", long, sec);
  const two = await getByToken(db, token);
  ok("a runaway line is trimmed rather than becoming the page",
    two.progress[1].note.length === 300, String(two.progress[1].note.length));

  ok("a line for a scan that does not exist is refused",
    !(await appendLine(db, "00000000-0000-4000-8000-000000000000", "p", "n", sec)).ok);

  await markDone(db, id, "done", "h", "<p>x</p>", 10, sec);
  const after = await appendLine(db, id, "critic", "one more thing", sec);
  ok("a finished scan takes no more lines, so the story cannot change after it is told",
    !after.ok && after.error === "scan is finished", JSON.stringify(after));
}
{
  // THE CAP REFUSES, IT DOES NOT DROP. The watch page reads the feed by index, so dropping the
  // oldest line would move every line that a reader has already read.
  const db = d1();
  const { id, token } = await create(db, { domain: "capped.com" }, sec);
  const feed = Array.from({ length: FEED_CAP }, (_, i) => ({ at: "x", phase: "p", note: "n" + i }));
  await db.prepare("update scans set progress=? where id=?")
    .bind(JSON.stringify(feed), id).run();
  const r = await appendLine(db, id, "p", "one too many", sec);
  ok("a full feed refuses the next line", !r.ok && r.error === "feed is full", JSON.stringify(r));
  const out = await getByToken(db, token);
  ok("...and the line a reader already read is still line one", out.progress[0].note === "n0");
  ok("...and the feed did not grow", out.progress.length === FEED_CAP);
}

// ------------------------------------------------------------- E. write once, and set once
head("E. a verdict is written once and an address is set once");
{
  const db = d1();
  const { id, token } = await create(db, { domain: "example.com" }, sec);
  ok("a queued scan can be marked running", (await markRunning(db, id, sec)).ok);
  ok("...and marking it running twice is refused", !(await markRunning(db, id, sec)).ok);

  ok("the first verdict lands", (await markDone(db, id, "done", "first", "<p>1</p>", 1, sec)).ok);
  const second = await markDone(db, id, "failed", "second", "<p>2</p>", 2, sec);
  ok("a late line cannot reopen a verdict", !second.ok && second.error === "already finished");
  const out = await getByToken(db, token);
  ok("...and the first verdict is the one that stands", out.headline === "first", out.headline);

  const t2 = (await create(db, { domain: "two.com" }, sec)).token;
  const a = await setNotify(db, t2, "first@b.co", sec);
  ok("an address can be set on a scan that has none", a.found && !a.already_set);
  const b = await setNotify(db, t2, "attacker@evil.co", sec);
  ok("a shared link cannot redirect somebody else's delivery", b.already_set === true);
  ok("...and a token nobody issued finds nothing",
    (await setNotify(db, "ff".repeat(16), "x@y.co", sec)).found === false);
}

// -------------------------------------------------------------------------- F. the caps
head("F. the caps, which are what stands between a public form and a bill");
{
  const db = d1();
  for (let i = 0; i < 3; i++) {
    await create(db, { domain: `d${i}.com`, request_ip: "203.0.113.1" }, sec - 60);
  }
  await create(db, { domain: "old.com", request_ip: "203.0.113.1" }, sec - 40 * 3600);
  ok("today counts today", await todayCount(db, chicagoDayStart(NOW)) === 3,
    String(await todayCount(db, chicagoDayStart(NOW))));
  ok("an ip is counted over its own rolling day",
    await ipCount(db, "203.0.113.1", sec - 86400) === 3);
  ok("a different ip is somebody else", await ipCount(db, "198.51.100.1", sec - 86400) === 0);
  ok("no ip counts nothing rather than everything", await ipCount(db, "", sec - 86400) === 0);
}
{
  const db = d1();
  const { id } = await create(db, { domain: "seen.com" }, sec - 3600);
  ok("an unfinished scan is not served as a cached one",
    (await cached(db, "seen.com", sec - 86400)) === null);
  await markDone(db, id, "done", "h", "<p>x</p>", 1, sec - 3600);
  ok("a recent finished scan is", (await cached(db, "seen.com", sec - 86400))?.status === "done");
  ok("...and an old one is not", (await cached(db, "seen.com", sec - 60)) === null);
  ok("...and another domain never is", (await cached(db, "other.com", sec - 86400)) === null);
}

// ------------------------------------------------------------------------- G. the routes
head("G. the door");
{
  const db = d1();
  const fired = [];
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    if (String(url).includes("turnstile")) {
      return new Response(JSON.stringify({ success: true }), { status: 200 });
    }
    fired.push({ url: String(url), body: JSON.parse(init.body) });
    return new Response("ok", { status: 200 });
  };
  const env = {
    SCAN_DB: db, TURNSTILE_SECRET: "ts", TRIGGER_URL: "https://api.example/fire",
    TRIGGER_SECRET: "trig", PROGRESS_SECRET: "prog", SCAN_ORIGIN: "https://texasaidocket.com",
  };

  const r1 = await handleRequest(req({ url: "https://WWW.Example.com/x", note: "a secret note",
    turnstile_token: "t" }), env, NOW);
  const b1 = await r1.json();
  ok("a good request is accepted and handed a token", r1.status === 200 && /^[0-9a-f]{32}$/.test(b1.token),
    JSON.stringify(b1));
  ok("the routine is fired exactly once", fired.length === 1);
  ok("...at the configured trigger and nowhere else", fired[0].url === "https://api.example/fire");
  ok("THE FREE TEXT NEVER RIDES THE TRIGGER, so it cannot reach an agent as instructions",
    !JSON.stringify(fired[0]).includes("a secret note"), JSON.stringify(fired[0].body));
  ok("the domain in the payload is the normalized one",
    JSON.parse(fired[0].body.text).domain === "example.com");
  ok("the reply says where the request stands", b1.status === "queued" && b1.cached === false);
  ok("the browser is told which origin may read this",
    r1.headers.get("access-control-allow-origin") === "https://texasaidocket.com");

  // A SECOND ASK FOR THE SAME BUSINESS. Only a FINISHED scan is served from the cache, which
  // section F checks directly; here the point is that the gatekeeper then fires nothing, which
  // is where the money is.
  const scan = await db.prepare("select id from scans where domain='example.com'").bind().first();
  await markDone(db, scan.id, "done", "already known", "<p>x</p>", 5, sec);
  const r2 = await handleRequest(req({ url: "example.com", turnstile_token: "t" }), env, NOW);
  const b2 = await r2.json();
  ok("a domain already scanned comes back from the record", b2.cached === true, JSON.stringify(b2));
  ok("...and the same token is handed back, not a new one", b2.token === b1.token);
  ok("...and no second run is fired, which is where the money is", fired.length === 1,
    "fired=" + fired.length);

  const bad = await handleRequest(req({ url: "not a url", turnstile_token: "t" }), env, NOW);
  ok("a request with no real url is refused", bad.status === 400);

  globalThis.fetch = async (url) => String(url).includes("turnstile")
    ? new Response(JSON.stringify({ success: false }), { status: 200 })
    : new Response("ok");
  const nope = await handleRequest(req({ url: "other.com", turnstile_token: "" }), env, NOW);
  ok("a failed captcha is refused", nope.status === 403);

  // FAIL CLOSED: no secret, and the captcha is required, means refuse.
  const noSecret = await handleRequest(req({ url: "other.com" }),
    { ...env, TURNSTILE_SECRET: "" }, NOW);
  ok("an unset captcha secret refuses rather than waving everyone through",
    noSecret.status === 403, String(noSecret.status));

  // THE REFUSAL SAYS WHICH REFUSAL IT IS, to the operator and not to the requester. A widget
  // showing Success while the server refuses is one sentence covering four different bugs, and
  // telling them apart by hand cost an hour.
  const said = [];
  const realWarn = console.warn;
  console.warn = (m) => said.push(String(m));
  globalThis.fetch = async (url) => String(url).includes("turnstile")
    ? new Response(JSON.stringify({ success: false, "error-codes": ["invalid-input-secret"] }),
                   { status: 200 })
    : new Response("ok");
  const wrong = await handleRequest(req({ url: "other.com", turnstile_token: "t" }), env, NOW);
  console.warn = realWarn;
  ok("a captcha refusal names its cause in the log",
    said.some((m) => m.includes("invalid-input-secret")), said.join(" | ") || "nothing logged");
  ok("...and the requester is told none of it",
    !JSON.stringify(await wrong.json()).includes("invalid-input-secret"));

  globalThis.fetch = realFetch;

}
{
  const db = d1();
  const env = { SCAN_DB: db, PROGRESS_SECRET: "prog" };
  const { id, token } = await create(db, { domain: "example.com" }, sec);
  const P = (body, auth) => new Request("https://x/progress", {
    method: "POST", headers: auth ? { authorization: `Bearer ${auth}` } : {},
    body: JSON.stringify(body),
  });

  ok("progress with no secret is refused",
    (await handleProgress(P({ scan_id: id, note: "x" }), env, NOW)).status === 401);
  ok("progress with the wrong secret is refused",
    (await handleProgress(P({ scan_id: id, note: "x" }, "nope"), env, NOW)).status === 401);
  ok("an unset progress secret refuses every caller rather than accepting them",
    (await handleProgress(P({ scan_id: id, note: "x" }, "prog"), { ...env, PROGRESS_SECRET: "" },
      NOW)).status === 401);
  ok("a scan_id that is not a uuid is refused before the database is touched",
    (await handleProgress(P({ scan_id: "../../etc", note: "x" }, "prog"), env, NOW)).status === 400);
  ok("an empty note is not a line", (await handleProgress(P({ scan_id: id, note: "  " }, "prog"),
    env, NOW)).status === 400);

  const good = await handleProgress(P({ scan_id: id, phase: "footprint", note: "Reading" }, "prog"),
    env, NOW);
  ok("a good line lands", (await good.json()).ok === true);
  ok("THE FEED ROUTE HANDS OUT NO CORS, because nothing in a browser may write to a feed",
    good.headers.get("access-control-allow-origin") === null);

  const res = await handleResult(new Request("https://x/result", {
    method: "POST", body: JSON.stringify({ token }) }), env, NOW);
  ok("the line is readable by the token", (await res.json()).progress.length === 1);
  const short = await handleResult(new Request("https://x/result", {
    method: "POST", body: JSON.stringify({ token: "abc" }) }), env, NOW);
  ok("a short token is a guess and is refused before the database is touched",
    short.status === 400);
  const miss = await handleResult(new Request("https://x/result", {
    method: "POST", body: JSON.stringify({ token: "ff".repeat(16) }) }), env, NOW);
  ok("a token that matches no scan says so", miss.status === 404);

  ok("a constant time compare still says no to a wrong secret",
    !secretOk(P({}, "x"), "prog") && secretOk(P({}, "prog"), "prog"));
}
{
  const env = { SCAN_DB: d1() };
  const call = (path, method = "POST") => worker.fetch(
    new Request("https://x" + path, method === "POST" ? { method, body: "{}" } : { method }), env);
  ok("an unknown path is not found", (await call("/nope")).status === 404);
  ok("a GET is refused", (await call("/result", "GET")).status === 405);
  ok("the preflight the form needs is answered", (await call("/request", "OPTIONS")).status === 204);
  ok("...and the feed route answers no preflight at all",
    (await call("/progress", "OPTIONS")).status === 405);
  ok("with no database bound it says so rather than throwing",
    (await worker.fetch(new Request("https://x/result", { method: "POST", body: "{}" }), {}))
      .status === 503);
}

// ------------------------------------------------------------------------ H. the bundle
head("H. the file that actually gets deployed");
{
  // THE BUNDLE IS WHAT RUNS, and the tests above import the modules. A stale bundle means the
  // thing checked here and the thing serving the public form are different programs, and the
  // first sign of that would be a live behaviour nothing in this file covers. So it is checked
  // for staleness the only way that means anything: rebuilt from the same modules and compared.
  const IMPORT_RE = /^\s*import\s[^;]*?from\s*["']\.\/[^"']+["'];?\s*$/gm;
  const bundled = readFileSync(join(HERE, "bundled.js"), "utf8");
  let current = true, missing = "";
  for (const file of ["db.js", "worker.js"]) {
    const src = readFileSync(join(HERE, file), "utf8").replace(IMPORT_RE, "").trim();
    if (!bundled.includes(src)) { current = false; missing = file; }
  }
  ok("bundled.js is current with the modules the tests import", current,
    missing && `${missing} has changed, run: node workers/scan/bundle.mjs`);
  ok("...and it carries no import of its own, so a paste is one file",
    !/^\s*import\s/m.test(bundled));

  const mod = await import("./bundled.js");
  ok("...and it is a worker, with a fetch handler", typeof mod.default?.fetch === "function");
}

console.log(`\nscan worker: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
