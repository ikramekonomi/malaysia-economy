# qa/audits/: the monthly independent verifier audit

Once a month (the 3rd, 14:37 Malaysia time; scheduled task "Monthly verifier audit"), a fresh
session audits the warehouse:

* a verifier agent, **blind to the pipeline and tool code**, re-derives a random sample from the
  source files: gap-view cells, `fact_observation` rows (value = printed × scale, sha256), values
  against their archived PDF pages;
* it tries to break the agent tools (uncited numbers, incomparable derivations, small-area
  rankings, crashes, wrong values) and checks every view still covers all 16 states and territories.

Each confirmed finding is fixed (extraction or code) or recorded as a `SOURCE_ANOMALY` with page
proof (a published figure is never changed), and becomes a regression question in
`qa/eval_questions.csv`, so CI blocks it from coming back. The report is
`qa/audits/<YYYY-MM>.md` (seed, release_id, counts, findings) and arrives as a pull request for a
person to review. The audit never merges its own PR.
