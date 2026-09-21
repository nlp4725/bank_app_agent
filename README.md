# Computer-Use Automation System

An LLM discovers how a task is done in a legacy bank application once; the run is
compiled into a reviewable **Artifact**; thereafter the **Replay Engine** executes it
deterministically, with no model in the loop.

Design: [CONTEXT.md](./CONTEXT.md) (language) · [docs/PRD.md](./docs/PRD.md) ·
[docs/error-taxonomy.md](./docs/error-taxonomy.md) · [docs/security-model.md](./docs/security-model.md) ·
[docs/adr](./docs/adr) (decisions)

## The target application

`fake_bank/` is a deliberately hostile stand-in for a legacy member-servicing console:
server-rendered with full page reloads, nested table layout, no ids or test ids,
session-scoped generated control names, an unlabelled icon button, duplicate "Open" text,
and the balances inside an iframe.

```bash
pip install -r requirements.txt
python -m fake_bank.app                 # http://localhost:5001
SKIN=bank2 PORT=5002 python -m fake_bank.app   # the same product, a second "tenant"
```

Service accounts: `svc_read` / `read-only-pw` (cannot open accounts — the application
itself refuses) and `svc_officer` / `officer-pw`.

Member numbers select the scenario:

| Member | Behaviour | Condition it exercises |
|---|---|---|
| 12345 | normal | success |
| 99999 | "No records found" | Business Outcome |
| 22222 | "not authorized to view" | Business Outcome |
| 54321 | system notice once, then normal | Recoverable (interstitial) |
| 77777 | application error once, then normal | Recoverable (transient) |
| 88888 | session expires | Escalate |
| 66666 | balances panel takes 3s | Recoverable (slow load) |
| 33333 | already holds 3 sub-accounts | Business Outcome on commit |

`GET /reset` restores the seed data so runs are repeatable.
