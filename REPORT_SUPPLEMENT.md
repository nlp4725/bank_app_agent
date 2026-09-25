# REPORT supplement

Material referenced from [REPORT.md](./REPORT.md) that is too long for its page budget.

## S1. A whole Artifact

The state machine drawn in Figure 2.1 of the report, and the schema listed in §2, with
every value filled in.

```json
{
  "capability": {"id": "member.read_savings_balance", "version": "1.0.0",
                 "vendor_app": "demo-core-servicing", "role": "balance_reader",
                 "status": "approved", "approvals": ["reviewer:nasi"]},

  "contract": {
    "inputs":  {"member_number": {"type": "string", "pattern": "^[0-9]{5}$", "max_length": 5,
                                  "sensitive": true, "required": true}},
    "outputs": {"savings_balance": {"type": "money", "sensitive": false}},
    "outcomes": [
      {"code": "MEMBER_NOT_FOUND", "meaning": "No member exists with that number.",
       "resolver": "member", "retry_same_inputs": "never",
       "caller_hint": "Confirm the 5-digit member number with the member and try again."},
      {"code": "NOT_AUTHORIZED", "meaning": "This login may not view that member.",
       "resolver": "institution_staff", "retry_same_inputs": "never",
       "caller_hint": "Have staff grant this login access to the member's records."}]},

  "needs": {"pages":   ["/login", "/members/*", "/search"],
            "actions": ["click", "read", "type"],
            "secrets": ["login_password", "login_username"]},

  "states": [
    {"id": "s1_login",                "checkpoint": {"type": "element_present", "target": "t_user_id"}},
    {"id": "s2_user_id_entered",      "checkpoint": {"type": "field_value", "target": "t_user_id", "non_empty": true}},
    {"id": "s3_password_entered",     "checkpoint": {"type": "field_value", "target": "t_password", "non_empty": true}},
    {"id": "s4_search",               "checkpoint": {"type": "element_present", "target": "t_member_number"}},
    {"id": "s5_member_number_entered","checkpoint": {"type": "field_value", "target": "t_member_number", "non_empty": true}},
    {"id": "s6_members_id",           "checkpoint": {"type": "element_present", "target": "t_savings_balance"}},
    {"id": "s7_savings_balance_read", "checkpoint": {"type": "element_present", "target": "t_savings_balance"},
                                      "terminal": "succeeded"}],

  "transitions": [
    {"from_state": "s1_login",                 "to_state": "s2_user_id_entered",
     "action": {"type": "type",  "target": "t_user_id",       "value_ref": "login_username"},  "risk": "safe"},
    {"from_state": "s2_user_id_entered",       "to_state": "s3_password_entered",
     "action": {"type": "type",  "target": "t_password",      "value_ref": "login_password"},  "risk": "safe"},
    {"from_state": "s3_password_entered",      "to_state": "s4_search",
     "action": {"type": "click", "target": "t_sign_in"},                                       "risk": "safe"},
    {"from_state": "s4_search",                "to_state": "s5_member_number_entered",
     "action": {"type": "type",  "target": "t_member_number", "value": "{{member_number}}"},   "risk": "safe"},
    {"from_state": "s5_member_number_entered", "to_state": "s6_members_id",
     "action": {"type": "click", "target": "t_member_number_button"},                          "risk": "safe"},
    {"from_state": "s6_members_id",            "to_state": "s7_savings_balance_read",
     "action": {"type": "read",  "target": "t_savings_balance", "into": "savings_balance"},    "risk": "safe"}],

  "targets": {
    "t_user_id":       {"rungs": [{"kind": "label_anchor", "anchor": "User ID",  "role": "textbox", "relation": "right_of"}]},
    "t_password":      {"rungs": [{"kind": "label_anchor", "anchor": "Password", "role": "textbox", "relation": "right_of"}]},
    "t_sign_in":       {"rungs": [{"kind": "role_name", "role": "button", "name": "Sign in"},
                                  {"kind": "picture", "asset": "artifacts/assets/member.read_savings_balance/03_target.png", "threshold": 0.94}]},
    "t_member_number": {"rungs": [{"kind": "label_anchor", "anchor": "Member number", "role": "textbox", "relation": "right_of"}]},
    "t_member_number_button":
                       {"rungs": [{"kind": "label_anchor", "anchor": "Member number", "role": "button", "relation": "right_of"},
                                  {"kind": "picture", "asset": "artifacts/assets/member.read_savings_balance/05_target.png", "threshold": 0.94}]},
    "t_savings_balance": {"frame": {"url_contains": "/panel"},
                       "rungs": [{"kind": "label_anchor", "anchor": "Savings balance", "relation": "right_of"}]}},

  "watchers": [
    {"id": "w_not_found",      "trigger": {"type": "text_present", "value": "No records found"},
     "condition": "business_outcome", "outcome": "MEMBER_NOT_FOUND", "provenance": "reuse:member.open_sub_account"},
    {"id": "w_not_authorized", "trigger": {"type": "text_present", "value": "not authorized to view"},
     "condition": "business_outcome", "outcome": "NOT_AUTHORIZED",   "provenance": "reuse:member.open_sub_account"}],

  "provenance": {"discovered_by": "disc_5d0cdc53", "contract_by": "reviewer",
                 "example_values": {"member_number": "12345"}}
}
```

**Figure S1 — A whole approved Artifact, verbatim from
[read_savings_balance.1.0.0.yaml](./artifacts/read_savings_balance.1.0.0.yaml).** *One
approval, because nothing in it commits. Success is not an Outcome Code: it is the Run
Result `Succeeded` carrying `outputs`, reached at the State marked `terminal: succeeded`;
Outcome Codes are only the legitimate non-happy answers. The Watchers were borrowed from
`open_sub_account` on the same app, which is what their provenance says. The balance is in
an iframe, hence the `frame` on its Target.*

### The schema, block by block

The schema listed in §2 of the report, adapted from PreAct, one block at a time:

- **capability** — the identity: id, version, the vendor app and Role it runs under,
  and whether it is a draft or approved. A draft never replays; approval names who
  signed it.
- **contract** — all a Calling Agent depends on. `inputs` are typed and validated
  before a browser opens; `outputs` are what a Succeeded result carries; `outcomes` are
  the legitimate non-happy answers such as `MEMBER_NOT_FOUND`, each with who can resolve
  it and a hint for the caller.
- **needs** — the pages, action types and secrets the flow was seen to use during
  discovery. Policy must grant every item or the run is Refused before anything runs.
- **states** — the screens the flow passes through, one after every action, each with
  a Checkpoint: the Predicate that must hold before the engine believes it is there.
  One State is marked terminal, which is what Succeeded means.
- **transitions** — the steps: one Action ("click", "type", "select" or "read") on one
  Target, from one State to the next, with its risk label and, when the Action commits,
  a Verification Check that answers "did it already happen?".
- **targets** — where an action lands: the control, described by the frame it lives in
  and a ladder of ways to find it, accessible name first, then the caption beside it,
  then a picture. Replay records which rung matched.
- **watchers** — the flow's own error handling: a trigger Predicate that recognises a
  screen, the Condition it is (business outcome, recoverable, escalate, hard failure),
  what to do about it, and where the Watcher came from. App-wide ones such as session
  expiry arrive from the App Profile at load time.
- **provenance** — which Discovery Run produced it, who fixed the Contract, and the
  example values used, so the transcript itself is not in the file and stays in that
  run's trail under evidence/.
- **predicate** — the grammar for every check in the file: the only four questions the
  engine can ask a screen, or a combination of them, never free text.

## S2. Four runs in full

Four replays of the chain in Figure 2.1 of the report, one row each.

![read_savings_balance under four runs](./docs/figures/read_savings_balance_paths.svg)

**Figure S2 — Figure 2.1 of the report under four real replays, drawn from their trails.** *The happy
path never leaves the chain. The other three miss the same Checkpoint and get three
answers: `99999` is a Business Outcome, stop with `MEMBER_NOT_FOUND`; `88888` is
Recoverable, the engine finds the login State holds and runs the chain again from there;
`44444` is an Escalate, a supervisor acts in the live browser and the run resumes at the
State that now holds.*

## S3. Defence in depth, the full table

The redaction chain of [docs/discovery.md](./docs/discovery.md) and REPORT §6 as a list; here every layer with the threat it counters, who
owns it, when it is enforced, what a failure there becomes, and what is not built.

| # | Layer · principle | Counters | Enforced by, and when | Owned by | A failure becomes | Not built, or weak |
|---|---|---|---|---|---|---|
| 1 | **Environment** · no model near production (ADR 0003) | a wrong or injected model acting on real Members; anything leaving the institution in production | the Tenant Policy's `environment` tag, refused in [`cua/discovery/run.py`](./cua/discovery/run.py) before a browser opens; the import-graph test in [`tests/app/governance/test_policy.py`](./tests/app/governance/test_policy.py) proves replay imports no model SDK | the Tenant tags each instance; the provider's package layout | Refused, no browser opened | credential separation by phase is deployment design |
| 2 | **Execution integrity** · an Artifact is data and the engine its only interpreter (ADR 0001) | an Artifact or Overlay that is wrong or tampered with; drift guessed through; a retry that repeats a commit | closed vocabularies in [`cua/domain/artifact.py`](./cua/domain/artifact.py): four Actions, four Predicates, and the schema rejects any other; [`cua/governance/overlay.py`](./cua/governance/overlay.py) rejects an Overlay that touches behaviour or widens Needs; [`cua/replay/engine.py`](./cua/replay/engine.py) stops on an Unknown State, never retries a Business Outcome, and looks (Verification Check) before it clicks again | the provider; an Artifact changes only by a new reviewed version | rejected at load; at run, Failed or Outcome Unknown, never a guess | a Fallback Match is allowed and only logged; its rising rate is the drift signal, not a stop |
| 3 | **Network** · allowlisted origins, on every request | exfiltration the page starts itself: `/leaky` renders a 1×1 image with member data in its URL; a cookie crossing Tenants; downloads, popups, permission prompts | a route gate in [`cua/surface/driver.py`](./cua/surface/driver.py) on every request the browser makes, page-initiated included; downloads off, extra pages closed, permissions denied, dialogs dismissed, a fresh context per run; a test proves only the Surface module touches the browser | the Tenant declares its origins in the Allowlist; the provider's driver enforces | the request is aborted and logged; an undeclared origin is Refused before a browser opens | enforced in the browser; an egress allowlist at the container is design only |
| 4 | **Authorization** · Baseline ∩ Role ∩ Tenant grant ∩ Needs (ADR 0005) | a capability run where its Tenant never granted it; an Artifact using a page or action outside its Role; a read Role committing | [`cua/governance/policy.py`](./cua/governance/policy.py) over four files owned by four parties: at approval (Needs must fit the Role), before a browser opens, and before every action; each layer may narrow, none may widen | Baseline: the provider · Role: a Reviewer, before discovery · grant: the Tenant · Needs: what the Discovery Run did | Refused, naming the layer that refused: a guarantee of no side effects | the route keyword deny-list is a weak second net |
| 5 | **Identity** · least privilege inside the app itself | every layer above failing at once | the Tenant's app, signed into as the Role's Service Account, resolved at the keystroke by [`cua/secrets.py`](./cua/secrets.py): `balance_reader` signs in as `svc_read`, which has no sub-account form | the Tenant, which issues the account | the app refuses; the run Fails with evidence | — |
| 6 | **Change control** · Consequential by default; two named approvals; separation of duties (ADR 0002) | an unreviewed or unverifiable commit; one person approving their own work; a Reviewer reaching a live session | [`cua/authoring/lint.py`](./cua/authoring/lint.py) and [`review.py`](./cua/authoring/review.py): every click arrives Consequential and only a Reviewer may mark it Safe; a discovery literal or an unfilled placeholder fails the lint; two approvals for an Artifact that commits; a Verify Replay on inputs discovery never saw; a Verification Check per Consequential Action; every Consequential Action waits for an Operator's approval, and a capability that commits is Refused unattended; the engine refuses any Artifact not marked approved, and the Capability Store never lets a re-review displace an approved version | the Reviewer approves and never sees a live session; the Operator alone touches one; the Recorder decides nothing | not approved; a commit with nobody on shift is Refused before a browser opens | no identity system behind Reviewer and Operator names |
| 7 | **Data** · default-deny at one chokepoint (Figure 6.2) | Member data reaching a model, a log, a screenshot or an Artifact; a Secret reaching anything | [`cua/evidence/redact.py`](./cua/evidence/redact.py) on the way to a model and on the way to evidence; Secrets by name, substituted at the keystroke; evidence records identifiers we generated, never page text; outputs to the caller in full, masked in the record | the Reviewer declares Readable and Sensitive Regions in the App Profile, per app, not per capability | hidden; a canary value never appears in evidence (test) | pixels: a control is never painted |
| 8 | **Audit** · append-only, write-ahead | a silent action; a crash mid-commit passing as a mere failure; unexplained drift | [`cua/evidence/writer.py`](./cua/evidence/writer.py): one writer, a line flushed before every action, every policy decision and every matched rung recorded; on restart an in-flight commit closes as Outcome Unknown | the provider writes; the Operator reads during a run, the Reviewer after | Outcome Unknown: a person looks, nobody retries | a hash chain for tamper evidence is design only |

**Figure S3 — Eight layers, read outside in.** *The last column is the residual risk
register that "Limits, plainly" in the report refers to.*

## S4. Every surprise becomes one of four Conditions

The table §3 of the report summarises: each runtime condition, who can act on it, the engine's reaction, and the Run Result the caller sees if it is not resolved.

| Example on screen | Condition | Who acts | Reaction | Run Result if unresolved |
|---|---|---|---|---|
| Input fails its Contract type/pattern/enum | — (caught before the run) | nobody needed | never started | **Refused** |
| A capability that commits, with nobody on shift | — (caught before the run) | an Operator, next time | never started | **Refused** |
| The click that commits | Consequential/risky Action | Operator, live | pause, show the control and its rung, click only on approval | **Aborted**, **Failed** on timeout; nothing committed |
| "No records found" | Business Outcome | nobody — it is the answer | stop | **Business Outcome** `MEMBER_NOT_FOUND` (resolver: Member) |
| "You are not authorized to view this member" | Business Outcome | institution staff, later | stop | **Business Outcome** `NOT_AUTHORIZED` (resolver: institution staff) |
| "Amount exceeds available balance", "maximum accounts reached" | Business Outcome | the Member, by supplying different input | stop | **Business Outcome** `VALIDATION_REJECTED` or a specific code |
| "System notice" interstitial | Recoverable | system | dismiss, re-check, continue | — (invisible when it works) |
| Slow or blank page, transient error | Recoverable | system | wait, retry, bounded, Safe Actions only | **Failed** when the budget runs out |
| Session expired, login page returns | Recoverable | system | sign in again with the Service Account, re-observe, continue | **Failed** when the budget runs out |
| A screen only a person's own credential clears (supervisor ID and PIN) | Escalate | Operator, live | pause, hand over the session, resume on the Checkpoint | **Aborted**, **Failed** on timeout — or **Outcome Unknown** if a Consequential/risky Action was already in flight |
| "Application error" / stack trace | Hard Failure | nobody | stop with evidence | **Failed** |
| A screen matching neither Checkpoint nor Watcher | Unknown State | Operator if Attended; Reviewer later | never guess through | **Failed** (Unattended) |
| Frozen screen after a Consequential/risky Action | Unknown State | system first (Verification Check), else Operator | look, never click again | **Outcome Unknown** |
| System died mid-Consequential/risky Action | — | a person, afterwards | write-ahead log detects it on restart | **Outcome Unknown** |

**Figure S4 — Every surprise becomes one of four Conditions, and the test is who can
act.** *The system alone within a budget, a person during the run, or nobody in time. The
table is the one in [CONTEXT.md](./CONTEXT.md); budgets are in
[docs/error-taxonomy.md](./docs/error-taxonomy.md).*

## S5. Watchers live at two levels

| Level | Lives in | Watcher | Condition (see Figure S4) | Learnt how |
|---|---|---|---|---|
| **App-wide** | App Profile ([`config/profiles/demo-core-servicing.yaml`](./config/profiles/demo-core-servicing.yaml)), shared by every capability on the app | `w_session_expired` | Recoverable | added by a Reviewer after watching a run recover when an Operator pressed Resume without typing |
| | | `w_system_notice` | Recoverable | discovery clicked "OK" on the notice; the Reviewer made that click a Watcher, not a step |
| | | `w_approval_required` | Escalate | added by a Reviewer: only a supervisor's own credential clears it |
| **Capability-specific** | the Artifact itself, alongside the Contract's Outcome Codes | `w_not_found` | Business Outcome `MEMBER_NOT_FOUND` | a second Discovery Run on member 99999 ended `report_outcome`; provenance `disc_0a3f513c` |
| | | `w_not_authorized` | Business Outcome `NOT_AUTHORIZED` | added by a Reviewer by hand; provenance `reviewer:nasi` |

**Figure S5 — Watchers live at two levels, and each records where it came from.** *How a
Condition is handled is Figure S4; this is where the Watcher that names it lives. The
Capability Store merges the App Profile's Watchers into the Artifact at load time, so
app-wide knowledge is learnt once and reaches every capability; where both declare the
same id, the Artifact's wins. A capability-specific Watcher that names an Outcome Code
must have that code in the Contract, and every declared code must have a Watcher that can
produce it: the lint refuses either alone. An unknown condition, such as
`MAX_ACCOUNTS_REACHED` for member 33333, is an Unknown State until a Reviewer turns the
evidence into a new Watcher, which is a new Artifact version.*
