"""The hand-written Artifact for `open_sub_account`, and a test-only Tenant Overlay.

The App Profile that used to live here now has a home of its own —
`config/profiles/demo-core-servicing.yaml`, read through `cua.profile.load_profile` —
because it is governance data a Reviewer owns, not test scaffolding.

Every Target here was checked against the running demo app with
`tools/a11y_dump.py`: rung 1 (role+name) resolves buttons and links only, so every
text field is reached by its visible caption instead. See docs/targeting.md.

This is also the ground truth the Replay Engine is built against, before any model
is involved, and the yardstick a discovered Artifact is compared with later.
"""

from copy import deepcopy

_ARTIFACT = {
    "schema_version": 1,
    "capability": {
        "id": "member.open_sub_account",
        "version": "1.0.0",
        "vendor_app": "demo-core-servicing",
        "role": "account_opener",
        "status": "approved",
        "approvals": ["reviewer:nasi", "reviewer:sam"],
        "description": "Open a sub-account for a member and return the new account number.",
    },
    "contract": {
        "inputs": {
            "member_number": {"type": "string", "pattern": r"^[0-9]{5}$", "sensitive": True},
            "account_type": {"type": "enum", "values": ["savings", "checking", "holiday"]},
            "nickname": {"type": "string", "max_length": 20},
        },
        "outputs": {
            "savings_balance": {"type": "money", "sensitive": True},
            "new_account_number": {"type": "string"},
        },
        "outcomes": [
            {"code": "MEMBER_NOT_FOUND", "meaning": "No member exists with that number.",
             "resolver": "member", "caller_hint": "Ask the member to re-check the number."},
            {"code": "NOT_AUTHORIZED", "meaning": "This login may not view that member.",
             "resolver": "institution_staff"},
            {"code": "VALIDATION_REJECTED", "meaning": "The application rejected the values.",
             "resolver": "member",
             "data": {"message": {"type": "string", "redacted": True}}},
        ],
    },
    "needs": {
        "pages": ["/login", "/search", "/members", "/members/*"],
        "actions": ["type", "click", "select", "read"],
        "secrets": ["login_username", "login_password"],
    },
    "targets": {
        "t_user": {"rungs": [
            {"kind": "label_anchor", "anchor": "User ID", "role": "textbox"}]},
        "t_password": {"rungs": [
            {"kind": "label_anchor", "anchor": "Password", "role": "textbox"}]},
        "t_signin": {"rungs": [
            {"kind": "role_name", "role": "button", "name": "Sign in"}]},
        "t_member_field": {"rungs": [
            {"kind": "label_anchor", "anchor": "Member number", "role": "textbox"}]},
        "t_search": {"rungs": [
            {"kind": "role_name", "role": "button", "name": "Search"},
            {"kind": "label_anchor", "anchor": "Member number", "role": "button"},
            {"kind": "picture", "asset": "assets/search_icon.png"}]},
        "t_balance": {
            "frame": {"url_contains": "/panel"},
            "rungs": [{"kind": "label_anchor", "anchor": "Savings balance"}]},
        "t_open": {"rungs": [
            {"kind": "role_name", "role": "button", "name": "Open"}]},
        "t_acct_type": {"rungs": [
            {"kind": "label_anchor", "anchor": "Account type", "role": "combobox"}]},
        "t_nickname": {"rungs": [
            {"kind": "label_anchor", "anchor": "Nickname", "role": "textbox"}]},
        "t_review": {"rungs": [
            {"kind": "role_name", "role": "button", "name": "Review"}]},
        "t_commit": {"rungs": [
            {"kind": "role_name", "role": "button", "name": "Continue"}]},
        "t_new_number": {"rungs": [
            {"kind": "label_anchor", "anchor": "New account number"}]},
    },
    "states": [
        {"id": "sign_in", "checkpoint": {"type": "element_present", "target": "t_password"}},
        {"id": "search_ready", "checkpoint": {"type": "element_present", "target": "t_member_field"}},
        {"id": "member_open", "checkpoint": {"type": "text_present", "value": "Open Accounts"}},
        {"id": "balance_read", "checkpoint": {"type": "element_present", "target": "t_balance"}},
        {"id": "form_open", "checkpoint": {"type": "element_present", "target": "t_nickname"}},
        {"id": "review_shown", "checkpoint": {"type": "text_present", "value": "Review sub-account"}},
        {"id": "done", "terminal": "succeeded",
         "checkpoint": {"type": "text_present", "value": "Confirmation"}},
    ],
    "transitions": [
        {"from_state": "sign_in", "to_state": "sign_in", "risk": "safe",
         "action": {"type": "type", "target": "t_user", "value_ref": "login_username"}},
        {"from_state": "sign_in", "to_state": "sign_in", "risk": "safe",
         "action": {"type": "type", "target": "t_password", "value_ref": "login_password"}},
        {"from_state": "sign_in", "to_state": "search_ready", "risk": "safe",
         "action": {"type": "click", "target": "t_signin"}},
        {"from_state": "search_ready", "to_state": "search_ready", "risk": "safe",
         "action": {"type": "type", "target": "t_member_field", "value": "{{member_number}}"}},
        {"from_state": "search_ready", "to_state": "member_open", "risk": "safe", "timeout_ms": 8000,
         "action": {"type": "click", "target": "t_search"}},
        {"from_state": "member_open", "to_state": "balance_read", "risk": "safe", "timeout_ms": 8000,
         "action": {"type": "read", "target": "t_balance", "into": "savings_balance"}},
        {"from_state": "balance_read", "to_state": "form_open", "risk": "safe",
         "action": {"type": "click", "target": "t_open"}},
        {"from_state": "form_open", "to_state": "form_open", "risk": "safe",
         "action": {"type": "select", "target": "t_acct_type", "value": "{{account_type}}"}},
        {"from_state": "form_open", "to_state": "form_open", "risk": "safe",
         "action": {"type": "type", "target": "t_nickname", "value": "{{nickname}}"}},
        {"from_state": "form_open", "to_state": "review_shown", "risk": "safe",
         "action": {"type": "click", "target": "t_review"}},
        {"from_state": "review_shown", "to_state": "done", "risk": "consequential",
         "action": {"type": "click", "target": "t_commit"},
         "risk_suggestion": "creates the account: the next screen shows a new account number",
         "verify_effect": {"goto": "/members/{{member_number}}",
                           "predicate": {"type": "text_present", "value": "{{nickname}}"}}},
        {"from_state": "done", "to_state": "done", "risk": "safe",
         "action": {"type": "read", "target": "t_new_number", "into": "new_account_number"}},
    ],
    "watchers": [
        {"id": "w_not_found",
         "trigger": {"type": "text_present", "value": "No records found"},
         "condition": "business_outcome", "outcome": "MEMBER_NOT_FOUND",
         "provenance": "discovery_run_2"},
        {"id": "w_not_authorized",
         "trigger": {"type": "text_present", "value": "not authorized to view"},
         "condition": "business_outcome", "outcome": "NOT_AUTHORIZED",
         "provenance": "reviewer:nasi"},
        {"id": "w_validation",
         "trigger": {"type": "text_present", "value": "is required"},
         "condition": "business_outcome", "outcome": "VALIDATION_REJECTED",
         "extract": {"field": {"from": "regex", "pattern": r"^(\w+) is required"}},
         "provenance": "reviewer:nasi"},
    ],
    # MAX_ACCOUNTS_REACHED is deliberately absent: member 33333 is the held-out
    # condition that must produce an Unknown State until a Reviewer adds a Watcher.
    "provenance": {
        "discovered_by": "discovery_run_1",
        "contract_by": "reviewer:nasi",
        "example_values": {"member_number": "54321", "nickname": "Holiday fund"},
    },
}

_OVERLAY = {
    "base_artifact": "member.open_sub_account@1.0.0",
    "tenant": "bank_b",
    "origin": "http://localhost:5002",
    "targets": {
        "t_member_field": {"rungs": [
            {"kind": "label_anchor", "anchor": "Find member by #", "role": "textbox"}]},
        "t_search": {"rungs": [
            {"kind": "label_anchor", "anchor": "Find member by #", "role": "button",
             "relation": "nearest"},
            {"kind": "picture", "asset": "assets/find_icon.png"}]},
        "t_open": {"rungs": [{"kind": "role_name", "role": "button", "name": "Create"}]},
        "t_commit": {"rungs": [{"kind": "role_name", "role": "button", "name": "Submit"}]},
    },
}


def artifact_dict():
    return deepcopy(_ARTIFACT)


def overlay_dict():
    return deepcopy(_OVERLAY)
