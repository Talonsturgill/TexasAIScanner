-- 002_progress: the write side of the feed the read side already returns.
--
-- WHY THIS EXISTS. `scanner_get_by_token` has always returned `progress` and, once finished,
-- `result_html`, and until now NOTHING WROTE EITHER. The reading half of a live view was built
-- and deployed; the writing half was never started, so the feed was always the empty array the
-- column defaults to and a finished scan never landed back on its own row. Three functions
-- close that, and no more than three: append a line, say it started, say it finished.
--
-- SERVICE ROLE ONLY, like every other scanner_ function here. The routine does not hold this
-- key. It calls the `scan-progress` Edge Function, which holds an append-only secret, so a
-- leak of what the routine carries can add a line to one scan and can read nothing at all.
--
-- Apply to the texas-ai-scanner project (fbcxboktppalytugeqin) as migration `scanner_progress`.

-- A LINE OF THE FEED, APPENDED. Bounded on purpose in three ways, because this row is served
-- to a stranger's browser and is written by a long-running agent:
--
--   the note is TRIMMED, so one runaway line cannot become the page
--   the feed is CAPPED, so a loop cannot grow the row without limit
--   a finished or failed scan REFUSES more, so the story cannot change after it is told
--
-- THE CAP IS SET FOR DEPTH, NOT FOR A SUMMARY. The owner's call is that the run should report
-- as much as it honestly can while it is in flight, because the thing worth showing is how far
-- the search actually went. A scan that reads twenty pages and checks thirty published sources
-- should be able to say so line by line. Six hundred is roughly an order of magnitude above a
-- thorough run and still bounded, which is what a cap is for: it stops a loop, it does not
-- ration the reporting.
--
-- What a note may say is a matter for the routine and its prompt, not for SQL. The rule there
-- is that it describes THIS scan's own progress and never quotes the requester's free text,
-- which arrived from a stranger through a public form.
create or replace function public.scanner_progress(
  p_id uuid, p_phase text, p_note text)
  returns jsonb language plpgsql security definer set search_path = '' as $$
declare v record;
begin
  select id, status, jsonb_array_length(progress) as n
    into v from scanner.scans where id = p_id;
  if not found then
    return jsonb_build_object('ok', false, 'error', 'no such scan');
  end if;
  if v.status in ('done', 'degraded', 'failed') then
    return jsonb_build_object('ok', false, 'error', 'scan is finished');
  end if;
  if v.n >= 600 then
    return jsonb_build_object('ok', false, 'error', 'feed is full');
  end if;

  update scanner.scans
     set progress = progress || jsonb_build_object(
           'at', to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
           'phase', left(coalesce(p_phase, ''), 40),
           'note',  left(coalesce(p_note, ''), 300)),
         status = case when status = 'queued' then 'running' else status end
   where id = p_id;

  return jsonb_build_object('ok', true);
end;
$$;

-- The run has started. Separate from the first progress line because a scan can be picked up
-- and say nothing for a while, and "queued" and "running" are different things to a reader
-- watching a page.
create or replace function public.scanner_mark_running(p_id uuid)
  returns jsonb language plpgsql security definer set search_path = '' as $$
begin
  update scanner.scans set status = 'running'
   where id = p_id and status = 'queued';
  if not found then
    return jsonb_build_object('ok', false, 'error', 'not queued');
  end if;
  return jsonb_build_object('ok', true);
end;
$$;

-- The run finished. `p_degraded` carries the honesty gate's verdict: the scan ran and produced
-- something the critic would not fully pass, which is a different outcome from both a clean
-- pass and a failure, and the schema already has the status for it.
--
-- WRITE ONCE. A finished scan is not rewritten, because its token is shareable and a reader
-- who has already read the result should not find a different one behind the same link.
create or replace function public.scanner_mark_done(
  p_id uuid, p_headline text, p_html text, p_scan jsonb, p_degraded boolean default false)
  returns jsonb language plpgsql security definer set search_path = '' as $$
declare v record;
begin
  select status into v from scanner.scans where id = p_id;
  if not found then
    return jsonb_build_object('ok', false, 'error', 'no such scan');
  end if;
  if v.status in ('done', 'degraded') then
    return jsonb_build_object('ok', false, 'error', 'already finished');
  end if;

  update scanner.scans
     set status      = case when p_degraded then 'degraded' else 'done' end,
         headline    = left(coalesce(p_headline, ''), 300),
         result_html = p_html,
         scan_json   = p_scan,
         run_ms      = greatest(0, extract(epoch from (now() - created_at)) * 1000)::int
   where id = p_id;

  return jsonb_build_object('ok', true);
end;
$$;
