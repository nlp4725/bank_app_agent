# Brief coverage check

Every question or requirement in the assignment brief
([docs/Assignment A — Computer-Use Automation System (1).pdf](./Assignment%20A%20—%20Computer-Use%20Automation%20System%20(1).pdf)),
with where REPORT.md answers it and how well. Checked 24 Sep 2026 against the uncommitted
REPORT.md.

**Status, 25 Sep 2026.** Items 1 and 3 to 6 of the list at the bottom were applied to
REPORT.md, and Figure 6.1's table moved to the supplement as Figure S3. Item 2, the three
§1 paragraphs on stack, loop shape and the target app, was applied and then removed by
choice, so the four **No** rows under "Section 4" stand; the README covers them. What remains: length. The report is about 4,000 words with six figures
and two tables, over the brief's three pages, kept knowingly because every cut left would
remove an answer the brief asks for by name.

Verdicts: **Yes** = answered and easy to find · **Partial** = answered in the repo but the
report only hints at it, or leaves out a piece the brief names · **No** = not in the report.

---

## Section 3.1 — Goal-driven agent loop

**Q: Accept a goal plus a target (app / URL / entry point) as input.**
Report: §1 caption, "A Reviewer states a goal and confirms the Contract the LLM proposes."
The target is never mentioned; in the code it comes from the Tenant's Policy file, not a flag.
**Partial.** One clause: "the target is the origin the Tenant's Policy declares for that app".

**Q: Run an observe → decide → act loop until the goal is met or a stopping condition
(max steps, timeout, dead-end).**
Report: §1 "one policy-checked action per turn"; §5 "during discovery the model calling
`ask_human`, and a stuck detector". The stopping conditions are not listed. The code has six
endings (`goal_reached`, `report_outcome`, `ask_human`, `give_up` chosen by the model;
`step_limit`/`timeout`, `stuck_detected` decided by the code).
**Partial.** One sentence in §1 naming the six endings.

**Q: Actually interact with a real UI; bias toward an approach that works with no clean DOM.**
Report: Figure 4.1 (screenshot plus accessibility list, the unlabelled icon found by its
caption); §6 "What a model sees, and when".
**Yes.**

**Q (from §4 of the brief): LLM provider and model, and how you prompt and structure the
agent loop — defend it.**
Report: the model is named only in §7 as a thing not compared (`claude-opus-5`). Nothing on
why that model, what it is shown each turn, or that it answers with one tool call from a
closed set. The README covers all of this.
**No.** Three sentences in §1.

## Section 3.2 — Structured artifact

**Q: Ordered steps / actions.** Figures 2.1 and 2.2, states and transitions. **Yes.**

**Q: How each target is identified, with reasoning about robustness.**
Report: §4 first paragraph, the ladder. The reasoning table (what each rung reads, survives,
breaks on) is in CONTEXT.md and only linked.
**Yes**, but graders read reports side by side; the three-row table is cheap to inline.

**Q: Typed input parameters.** Figure 2.2 contract.inputs with type, pattern, sensitive. **Yes.**

**Q: Typed outputs and their shape.** Figure 2.2 contract.outputs; Figure S1. **Yes.**

**Q: A checkpoint or success condition.** One Checkpoint per State, a terminal State. **Yes.**

**Q: Decoupled from the raw model transcript.**
Report: provenance links the run by id. It never says in words that the transcript is not in
the artifact.
**Partial.** Half a sentence in the Figure 2.2 caption.

**Q: Versioned and reviewable; human and calling agent can both understand it.**
Report: capability.version, status, approvals; §6 row 6 (review, two approvals, decisions
file); §7 admits versioning is one-deep.
**Yes.**

**Q: Why you shaped the schema that way.**
Report: Figure 2.2 caption, "Four blocks are additions the bank setting forces", each named.
**Yes.**

**Q (brief §4): How the artifact is stored and serialized.**
Report: not stated. YAML files under artifacts/, resolved by the Capability Store.
**Partial.** One clause.

## Section 3.3 — Deterministic replay

**Q: Replay without invoking the LLM for decisions.**
Report: header, §6 row 1 (import-graph test proves it). **Yes.**

**Q: Stable targeting, verify the checkpoint, return declared outputs.**
Report: Figure 3.1, Figure 3.2, §2. **Yes.**

**Q: Detect and respond to each runtime condition: validation error, record not found,
permission denial, unexpected dialog, session timeout, slow or failed load.**
Report: Figure 3.2 has a row for every one of these, with who acts and the Run Result.
**Yes**, thorough.

**Q: Distinguish expected business outcomes, recoverable conditions and hard failures in the
result contract.**
Report: Figure 3.2 and the Run Result bullet; four Conditions plus Unknown State, and the
extra "Escalate" bucket is justified ("the test is who can act").
**Yes.**

**Q: A failure must carry enough to debug: what step, what was expected, what was observed.**
Report: the Run Result bullet names the six statuses but never says what `Failed` carries.
The words "expected" and "observed" do not appear as result fields anywhere in REPORT.md.
The envelope is in docs/error-taxonomy.md and the trail records `checkpoint_missed` with
step, predicate, expected target and URL.
**Partial.** One line: "Failed carries the step, the predicate expected, what was observed,
and an evidence id."

**Q: How determinism is achieved (locator strategy, fallbacks, waiting).**
Report: Figure 3.1 covers order and locators. The uncommitted rewrite dropped the old
caption's list ("no model, a closed vocabulary, the matched rung recorded, a Checkpoint after
every action, placeholders enforced by lint, waits through the browser, a loop guard").
"Wait" now appears once, in a table cell. The brief's criteria name "locator, wait, and
checkpoint strategy" together.
**Partial.** Restore one sentence on waiting: the engine observes until the Transition's
`timeout_ms`, resolve has its own timeout, budgets are engine defaults overridable per
Transition and visible in review.

**Q: Secondarily, any UI drift (this is under heading 3 in the brief).**
Report: drift is answered in §4 only. §3 does not point there.
**Partial.** One cross-reference sentence at the end of §3.

## Section 3.4 — Safety and policy guardrails

**Q: An explicit, configurable allowlist: domains / routes and action types.**
Report: Figure 6.1 rows 3 and 4; four files owned by four parties; route interception on
every request. **Yes.**

**Q: Distinguish safe from risky actions; handle risky conservatively (block, confirm or
flag) and justify it.**
Report: row 6, Consequential by default; unattended commit without a Verification Check is
Refused. What happens in an attended run is never stated in the report. In the code and the
evidence trail the Operator must approve the click and is shown which rung matched
(`operator_approval_required`).
**Partial.** One sentence: "Attended, the Operator approves each Consequential click and sees
which Target matched; unattended, it is Refused unless it carries a Verification Check."

**Q: Never persist secrets or raw sensitive data into artifacts or logs; redact.**
Report: row 7, Figure 6.2, secrets by reference at the keystroke, evidence holds only
generated identifiers. **Yes**, thorough. (evidence/README.md admits the name reached the
model five times in run 01 before origin masking was extended to page text; the report does
not mention that. Worth one honest clause under "Limits".)

**Q: Your guardrail model and its limits.**
Report: Figure 6.1 last column plus "Limits, plainly". **Yes.**

## Section 3.5 — Evidence and observability

**Q: A structured log of what the agent did and why.**
Report: row 8 lists what replay records (policy decisions, matched rung, write-ahead lines).
The discovery trail also records the model's `reason` for each proposal, which is the "why";
the report never says so, and there is no paragraph describing what a run folder holds.
**Partial.** Two sentences, in §1 or under row 8, describing the discovery trail
(observed, proposed with reason, policy decision, acted) and the replay trail.

**Q: At least one richer signal on failure.**
Report: §6, a masked screenshot on failure or escalation. **Yes.**

## Section 3.6 — Human-in-the-loop escalation and handoff

**Q: Detect a stuck state and raise an intervention request carrying capability, current
step, state or screenshot, and why.**
Report: §5 first bullet lists State, reason, live URL, screenshot, instruction. The capability
id is in the file but not in the list.
**Yes.**

**Q: The human operates the same live session, not a fresh one.**
Report: §5, "Same browser, same page"; Figure 5.1. **Yes.**

**Q: Hand control back so the run resumes; know who is in control.**
Report: the lease, Resume / Abort / auto-detect, resume re-checks the Checkpoint. **Yes.**

**Q: Preserve context and evidence across the handoff.**
Report: implied (one run, one trail) but not said.
**Partial.** Half a sentence.

**Q: Record what the human did.**
Report: "who, what decision, whether they navigated; never what they typed." The system does
not capture the person's individual clicks or fields touched. The brief asks to "capture the
human's actions". The report frames the thinner version as a privacy choice without saying
it is thinner.
**Partial.** Say plainly: clicks are not recorded, only identity, decision and URL change,
because the supervisor's PIN is the one thing the run must never hold; and name the design
for recording clicks with values hidden as a next step.

**Q: Stuck during discovery is one of the cases that must bring a human in.**
Report: §5 says stuck is detected "during discovery [by] the model calling `ask_human`, and a
stuck detector", which reads as if a handoff follows. In the code `ask_human` ends the
discovery run; nobody takes the live session, and the Reviewer re-runs.
**Partial, and currently misleading.** State that the handoff mechanism exists on the replay
path only, and that a discovery run that asks for a human ends with its evidence.

**Q: Mock the operator UI if needed, but make the mechanism real.**
Report: "The console is a mock Flask page; the lease, transfer, recording and auto-resume are
real." **Yes.**

## Section 3.7 — Heterogeneity and scale

**Q: Surface abstraction: the seam between perceiving/acting and the recorded flow; how it
extends to legacy web and desktop.**
Report: §4 first paragraph. Two problems. It says the Surface seam is "nine verbs" twice;
`ActingSurface` in cua/replay/context.py has thirteen methods (url, goto, text, wait, close,
screenshot, resolve, click, type, select, read, value_of, frame_urls) plus three attributes.
And the rewrite dropped the honest note that `url_matches` and `frame` are the web-shaped
parts of the schema.
**Partial.** Fix the count (or say "one Protocol of a dozen methods") and restore the
web-shaped note.

**Q: Multi-tenant reuse without re-recording per tenant; safe specialization.**
Report: Figure 4.2, demonstrated end to end, an Overlay that changes behaviour is refused.
**Yes**, strong.

**Q: Detect and manage per-tenant and per-version drift.**
Report: "Knowing when a tenant has drifted", Fallback Match rate per tenant per version;
designed, not built, and said so. **Yes.**

## Section 4 — "Explicitly your call": choose and defend in the write-up

| Choice | In REPORT.md? | Verdict |
|---|---|---|
| Language, runtime, frameworks | Python, Playwright and Flask are never named as choices ("Flask" appears once, about the mock console) | **No** |
| LLM provider / model, prompting, loop structure | see 3.1 above | **No** |
| Computer-use technology | Playwright is not named; the a11y-plus-screenshot observation is described | **Partial** |
| Target application and why | README describes the hostile Flask app; the report never argues why a local app over a public demo site (member number picks the scenario, no terms or PII, iframe, unlabelled control, two skins) | **No** |
| Artifact schema and storage | schema yes; storage no | Partial |
| Determinism on replay | Figure 3.1 | Yes |
| Architecture and boundaries: single process vs services, sync vs queued | not stated anywhere; "process" and "queue" appear zero times | **No** |
| The discovery run has to be real, evidence in /evidence/ | header links evidence/; runs 01, 02, 08 are real | Yes |

One paragraph in §1 covers the four "No" rows: one Python process, synchronous, Playwright
behind one Surface module, Flask stand-in chosen so the member number selects the condition,
Claude proposing one action per turn from a closed tool set.

## Section 5 and 6 — Scope and deliverables

**Q: A complete vertical slice touching every core requirement.** Yes, and the evidence
folder shows each leg.

**Q: Say what you cut and why, and what you would build next.** §7. **Yes.**

**Q: README with setup, keys, running without live services, and the exact demo commands.**
README.md. **Yes.**

**Q: REPORT.md, ~1 to 3 pages, the seven exact headings.**
Headings match exactly. Length does not: about 3,970 words including six figures and two
wide tables, roughly 2,300 words of prose. That renders to well over three pages. The
supplement already exists for this reason; the main file still needs cutting. The biggest
single item is the eight-row Figure 6.1 table, which is most of §6 and duplicates
docs/security-model.md.
**Partial.** Move Figure 6.1 to the supplement and keep an eight-line list, or accept the
length knowingly.

**Q: /evidence/ with an artifact, a discovery log, a replay log, and a replay that hits an
error.** Eight runs, including business outcome, unknown state and refused. **Yes.**

## Section 7 — Evaluation criteria not covered above

**Code quality: typed and tested where it counts.** The report mentions two tests that are
controls. It never says the suite is 190 tests against the live app with no mocks. Optional,
one line in §1 or §7.

## Section 8 — Stretch goals

| Stretch goal | Status | Said in the report? |
|---|---|---|
| Agent-facing capability catalog | `--list` only | Yes, §7 |
| Code generation | not done | Not mentioned; fine |
| Confidence and approval gate | approval gate done; reliability score not | Gate yes (§6 row 6); score is next-step 3 |
| Assisted LLM fallback on replay | rejected by design | Yes, §7 |
| Canonicalization / cross-tenant | done, demonstrated | Yes, §4 |
| Multi-run stability | not done | next-step 3 |

---

## What was changed, in order (applied)

1. "Nine verbs" is now "one Protocol of thirteen methods", with the web-shaped note back.
   §5 says the handoff exists on the replay path only and a stuck Discovery Run ends.
2. §1 gained three paragraphs: the stack and process boundary, the loop (what the model
   receives, the eight tools, the six endings, the limits), and why a hostile local app.
3. §3's Run Result bullet says what `Failed` carries.
4. Figure 3.1's caption lists what determinism is and how waiting works; §3 ends with a
   pointer to drift in §4.
5. §6 layer 6 states the attended rule; §5 says plainly that clicks are not captured.
6. §7 no longer says the loop is untested (it is, with a scripted model), and names the
   discovery-path handoff and a value-hiding click recorder as next step 5.
7. Figure 6.1's table is Figure S3 of the supplement; an eight-line list stays. The
   "Limits" paragraph also admits the run-01 page-text leak that evidence/README.md
   records.
