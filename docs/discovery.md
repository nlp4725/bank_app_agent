# Discovery — where an Artifact comes from

The half of the system with a model in it, end to end: the goal typed in words, the two
reviews, the flag-driven form for scripts, what the model sees and what it never sees, and
the same chain run from a committed discovery run with no key. Vocabulary in
[CONTEXT.md](./CONTEXT.md); the argument in [REPORT.md](../REPORT.md) §1 and §6. The
README's step 8 is the short form of this page.

Discovery only ever runs against a non-production environment; the code refuses otherwise
(ADR 0003). It needs `ANTHROPIC_API_KEY` in the environment or in a `.env` file.


**Start with a goal:**

```bash
python -m tools.start
```

```
What do you want to do today?: look up a member and read their savings balance

  capability  member.read_savings_balance
  role        balance_reader — View member information and balances.
  goal        Look up member {member_number} and read their current savings balance
  input       member_number      string  ^[0-9]{5}$  (sensitive)

  returns     succeeded         -> outputs:
                                   savings_balance    money
              business_outcome  -> one of:
                                   MEMBER_NOT_FOUND   resolver: member
                                   NOT_AUTHORIZED     resolver: institution_staff
                                   NO_SAVINGS_ACCOUNT resolver: member
              failed | refused | aborted | outcome_unknown  (engine; not reviewed here)

Approve this contract? [Y/n/e]  y
member_number [54321]: 12345
Watch the browser? [Y/n]  y
```

The model proposes the Contract and the narrowest Role from the goal; the Reviewer approves
it (`e` saves it to `contracts/` for editing first; `n` saves nothing). Then the browser
opens and the run is narrated turn by turn. When it reaches the goal, the **second review**
starts in the same terminal — the Artifact, the plan of steps the Recorder compiled:

```
  member.read_savings_balance 1.0.0   role balance_reader   status draft
  7 states, 6 steps, 0 watchers

  STEP 1   at s1_login      checkpoint: target t_user_id is on screen
           type   <secret login_username>
           into   target t_user_id  =  the textbox right of the caption "User ID"   (fallback: its picture)
           then   s2_user_id_entered      checkpoint: field t_user_id holds a value

  STEP 2   at s2_user_id_entered
           type   <secret login_password>
           into   target t_password  =  the textbox right of the caption "Password"   (fallback: its picture)
           then   s3_password_entered      checkpoint: field t_password holds a value

  STEP 3   at s3_password_entered
           click  target t_sign_in  =  the button named "Sign in"   (fallback: its picture)
           then   s4_search      checkpoint: target t_member_number is on screen
           risk   CONSEQUENTIAL  <- you decide: does this click commit anything?

  STEP 4   at s4_search
           type   '{{member_number}}'
           into   target t_member_number  =  the textbox right of the caption "Member number"   (fallback: its picture)
           then   s5_member_number_entered      checkpoint: field t_member_number holds a value

  STEP 5   at s5_member_number_entered
           click  target t_member_number_button  =  the button right of the caption "Member number"   (fallback: its picture)
           then   s6_members_id      checkpoint: target t_savings_balance is on screen
           risk   CONSEQUENTIAL  <- you decide: does this click commit anything?

  STEP 6   at s6_members_id
           read   target t_savings_balance  =  the control right of the caption "Savings balance", inside frame /panel   (fallback: its picture)
           into   output savings_balance
           then   s7_savings_balance_read      checkpoint: target t_savings_balance is on screen
           done   s7_savings_balance_read is terminal: SUCCEEDED

  WATCHERS   if a checkpoint fails, which screen is it?
           none yet  <- the next questions add them

Review this artifact now? [Y/n]  y

  STEP 3  click the button named "Sign in"   (target t_sign_in, s3_password_entered -> s4_search)
          is this action safe — it only navigates, commits nothing? [Y/n]  y
  STEP 5  click the button right of the caption "Member number"   (target t_member_number_button, s5_member_number_entered -> s6_members_id)
          is this action safe — it only navigates, commits nothing? [Y/n]  y
  MEMBER_NOT_FOUND: reuse watcher w_not_found — text 'No records found' (from member.open_sub_account)? [Y/n]  y
  NOT_AUTHORIZED: reuse watcher w_not_authorized — text 'not authorized to view' (from member.open_sub_account)? [Y/n]  y
  NO_SAVINGS_ACCOUNT: no watcher can recognise it yet. [t]ext on screen that means it, or [d]rop it from the contract  d
  approve as [reviewer:nasi]:

  decisions saved to artifacts/read_savings_balance.decisions.yaml
  lint, then verify-replay on member 54321 (discovery never saw it) with no model…

  APPROVED -> artifacts/read_savings_balance.1.0.0.yaml
  it is now live — replay it with no model:
    python -m tools.replay 12345 --capability member.read_savings_balance

  Watch it replay now, in a visible browser, 2s per step? [Y/n]  y
```

The two responsibilities behind those questions:

- **Risk.** Every "click" arrives Consequential/risky by default; "type", "select" and
  "read" arrive Safe. The Reviewer changes a click to Safe (the ones that only navigate)
  and leaves the unsafe ones as they are. During replay an unsafe action requires a human
  in the loop to confirm it, and if no human is present the run is refused automatically.
- **Error handling.** The current approach is prebuilt: an engineer drives the LLM through
  the known errors ahead of time, and each error's signature and how to deal with it is
  recorded as a Watcher, either before discovery or during it. The Reviewer chooses which
  to add to the capability (see Figures S4 and S5 of
  [REPORT_SUPPLEMENT.md](./REPORT_SUPPLEMENT.md)). We acknowledge the current approach is very manual and requires prior knowledge
  of the system and the workflow.

The Recorder decides nothing; each question is one it could not answer from the run. Every
click arrives Consequential and only a person downgrades it. A declared outcome needs a
watcher that can recognise it — borrowed from another approved capability on this app when
one exists — or it is dropped, because an answer the caller is promised but can never
receive is worse than none. The answers are a file, `artifacts/<name>.decisions.yaml`,
applied mechanically; approval is refused unless the result lints clean **and** replays
successfully, with no model, on a member the discovery run never saw. To redo a review,
give it the `runs/disc_…` folder your discovery printed, or the committed one:

```bash
python -m tools.start --review evidence/01-discovery-goal-reached
```

The flag-driven equivalent, for scripts:

```bash
ANTHROPIC_API_KEY=... python -m tools.discovery                 # the sub-account request, member 54321
ANTHROPIC_API_KEY=... python -m tools.discovery 99999           # same goal; expects report_outcome
```

**A goal is stated once, by a Reviewer, at discovery.** Production callers never state
goals — they invoke an approved capability by name with typed inputs (the README walkthrough). A
Discovery Request is three things, and only the first is free text:

| Part | Who owns it | What it does |
|---|---|---|
| **goal** | the Reviewer, in words | what the model reads every turn |
| **Role** | `config/roles/` | bounds the goal: pages, actions, whether it may commit |
| **Contract** | the Reviewer | fixes the capability's signature *before* any run |

`contracts/*.yaml` holds one request per capability; every flag overrides one field, and
the origin is never a flag — it comes from the Tenant's own Policy file:

```bash
# a different goal, under a Role that may not commit anything
ANTHROPIC_API_KEY=... python -m tools.discovery --contract contracts/read_balance.yaml
# or spell it out
ANTHROPIC_API_KEY=... python -m tools.discovery \
    --goal "Look up member {member_number} and read their current savings balance" \
    --contract contracts/read_balance.yaml --role balance_reader --tenant bank_a \
    --values member_number=12345
python -m tools.discovery --dry-run --contract contracts/read_balance.yaml   # no key: show the request
```

Type a goal that strays outside its Role — "wire $5,000 from member 12345" under
`balance_reader` — and every step the model proposes toward it is `policy_deny` (no
`/transfers` page in that Role, no commit allowed); three denials in a row and the run ends
`give_up`. The Role bounds the goal, not the wording.

The model gets a masked accessibility list plus a screenshot and proposes **one action per
turn**; code checks it against policy and performs it. It never sees a password, never sees a
value from a field that is not a declared Readable Region, and cannot name an action outside
the vocabulary. On success the Recorder compiles a draft Artifact immediately.

```
          A VALUE ON SCREEN
                │
       ┌────────▼─────────┐
       │ is it a password?│──yes──► (protected)      never read at all
       └────────┬─────────┘
                │ no
       ┌────────▼──────────────────┐
       │ is its Target declared a  │──no──► (hidden)  ← names, birthdays, and every
       │ Readable Region?          │                    field nobody has reviewed yet
       └────────┬──────────────────┘
                │ yes
       ┌────────▼─────────┐
       │ pattern net      │  SSN · card · email · phone · date · currency
       └────────┬─────────┘
                ▼
            recorded                and in the screenshot: undeclared value cells,
                                    Sensitive Regions and text patterns painted black
```

*Redaction: structural, origin, pattern, pixels. A value on screen reaches the model only
if it is not a password, sits in a declared Readable Region, and clears the pattern net.*

**Without a key**, the same chain runs from a saved discovery run:

```bash
python -m tools.inspect.show_run evidence/01-discovery-goal-reached   # what the model saw and asked for
python -m tools.authoring.record  evidence/01-discovery-goal-reached   # compile the draft + suggestions
python -m tools.authoring.approve evidence/01-discovery-goal-reached   # apply decisions, verify, approve
```

`record` prints what it could not decide for itself — "every click is marked Consequential:
mark the safe ones Safe", "action 6 clicks 'OK' on a page visited once: interruption or part
of the flow?". Those are questions for a person, answered in
[`artifacts/open_sub_account.decisions.yaml`](../artifacts/open_sub_account.decisions.yaml).

`approve` **rewrites `artifacts/open_sub_account.1.0.0.yaml` in place** — that is what
approval means here, and it is why the test suite still passes afterwards: the regenerated artifact
is equivalent to the committed one. It refuses to approve at all unless the result lints
clean *and* replays successfully on a member the discovery run never saw:

```
after review: 12 transitions, 3 watchers, 1 consequential
verify-replay on member 12345 (discovery never saw it)...
APPROVED -> artifacts/open_sub_account.1.0.0.yaml
```

It is idempotent — re-running it reproduces the committed artifact byte for byte on values
and assets.
