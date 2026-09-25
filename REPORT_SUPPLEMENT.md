# REPORT supplement

Material referenced from [REPORT.md](./REPORT.md) that is too long for its page budget.

## S1. A whole Artifact

The state machine drawn in Figure 2.1 of the report, and the schema of Figure 2.2, with
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

## S2. Four runs in full

The four replays summarised in Figure 3.4 of the report, one row each.

![read_savings_balance under four runs](./docs/figures/read_savings_balance_paths.svg)

**Figure S2 — Figure 2.1 of the report under four real replays, drawn from their trails.** *The happy
path never leaves the chain. The other three miss the same Checkpoint and get three
answers: `99999` is a Business Outcome, stop with `MEMBER_NOT_FOUND`; `88888` is
Recoverable, the engine finds the login State holds and runs the chain again from there;
`44444` is an Escalate, a supervisor acts in the live browser and the run resumes at the
State that now holds.*

