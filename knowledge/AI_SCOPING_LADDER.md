# The Feasibility Ladder (scan-scoped)

The conscience of the scan, and the reason a national tool can't fake it. A scanner that puts
every problem on the top rung is a sales form. This one names the LOWEST rung that clears the
bar, and says so when the answer is not AI at all.

## The ladder (name the LOWEST tier that clears the bar)

Every candidate bottleneck sits on a rung. Each step up costs reliability, money, latency and
explainability, and the step has to be earned by the problem rather than by excitement.

1. **RULES.** Deterministic software. Same input, same output, testable exhaustively. If inputs
   are structured and stable, stop here and say so.
2. **RETRIEVAL.** Lookup or search over their own data. No generation, so no hallucination
   surface.
3. **SINGLE_LLM.** One model call in a fixed spot. Messy input in, structured output out, and a
   human or a rule checks it.
4. **WORKFLOW.** The model runs inside fixed, testable steps. The default for real operations
   work.
5. **AGENT.** The model plans its own steps. The top rung, the most fragile, reserved for
   problems that genuinely need dynamic planning.

Most honest mid-market answers live on rungs 1 to 4. A scan that puts a common front-desk or
counting task on AGENT is almost always wrong.

## The four questions every observation must survive

- **COST OF ERROR.** What does a wrong answer cost this business, and who catches it before it
  lands. Costly and unforgiving, or full transparency required, means a human in the loop or a
  downgrade, never silent autonomy.
- **DATA READINESS.** Does the data exist, is it reachable or locked in a PDF or a phone system,
  is it labeled, representative, fresh and legal to use. If not, that gap IS part of the work.
  Say so rather than assuming it away.
- **COMPOUNDING ERROR.** For any multi-step or agentic idea, per-step reliability to the power
  of the step count collapses fast. Ninety five percent per step across twenty steps is about
  thirty six percent end to end. Minimise steps, add checkpoints, or downscope to a workflow.
- **AGENT WASHING.** If a candidate is a chatbot or an RPA script dressed as an autonomous
  agent, name it honestly and rescope it.

## When the honest answer is NOT AI (mark it, never hide it)

- The count or task is already captured by a scale, a barcode, an RFID read or a scan. If the
  number already exists, they don't need a model to see it.
- A sensor solves it cheaper than a camera model. A beam break or a plate reader beats computer
  vision unless real classification is required.
- A person clears it in a couple of minutes a few times a day. The economics need high
  frequency, high volume, or long hours of footage.
- It is safety or compliance critical with no human check. The cost of a wrong answer is too
  high to run unattended.
- The data doesn't exist or can't be reached. The gap is the project, and a scan should say so
  rather than pretend.

Saying "a rule does this cheaper and safer" is the trust proposition, not a lost sale. It is
what makes the would-help calls believable.

## The eval discipline (name it in every would-help observation)

Every real build needs a trusted baseline to grade against: the manual count, the manifest, the
record they already keep. No baseline, no eval, no promise. Run it beside the human for about
ninety days, then let the human spot-check. Saying this plainly is the difference between an
honest scan and a sales form.
