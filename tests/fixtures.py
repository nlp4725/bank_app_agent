"""A well-formed Artifact, used as the starting point for every rejection test."""

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
    },
    "contract": {
        "inputs": {
            "member_number": {"type": "string", "pattern": r"^[0-9]{5}$", "sensitive": True},
            "account_type": {"type": "enum", "values": ["savings", "checking", "holiday"]},
            "nickname": {"type": "string", "max_length": 20},
        },
        "outputs": {
            "savings_balance": {"type": "money"},
            "new_account_number": {"type": "string"},
        },
        "outcomes": [
            {
                "code": "MEMBER_NOT_FOUND",
                "meaning": "No member exists with that number.",
                "resolver": "member",
                "caller_hint": "Ask the member to re-check the number.",
            },
            {
                "code": "MAX_ACCOUNTS_REACHED",
                "meaning": "The member already holds the maximum number of sub-accounts.",
                "resolver": "institution_staff",
            },
        ],
    },
    "needs": {
        "pages": ["/login", "/search", "/members/*"],
        "actions": ["type", "click", "select", "read"],
        "secrets": ["login_username", "login_password"],
    },
    "states": [
        {"id": "sign_in_page", "checkpoint": {"type": "element_present", "target": "t_password"}},
        {"id": "logged_in", "checkpoint": {"type": "element_present", "target": "t_member_field"}},
        {
            "id": "member_open",
            "checkpoint": {"type": "text_present", "value": "Open Accounts"},
        },
        {"id": "balance_read", "checkpoint": {"type": "text_present", "value": "Savings balance"}},
        {"id": "form_open", "checkpoint": {"type": "element_present", "target": "t_nickname"}},
        {"id": "review_shown", "checkpoint": {"type": "text_present", "value": "Review sub-account"}},
        {
            "id": "done",
            "terminal": "succeeded",
            "checkpoint": {"type": "text_present", "value": "Confirmation"},
        },
    ],
    "transitions": [
        {
            "from_state": "sign_in_page",
            "to_state": "logged_in",
            "action": {"type": "type", "target": "t_password", "value_ref": "login_password"},
            "risk": "safe",
        },
        {
            "from_state": "logged_in",
            "to_state": "member_open",
            "action": {"type": "type", "target": "t_member_field", "value": "{{member_number}}"},
            "risk": "safe",
        },
        {
            "from_state": "member_open",
            "to_state": "balance_read",
            "action": {"type": "read", "target": "t_balance", "into": "savings_balance"},
            "risk": "safe",
        },
        {
            "from_state": "balance_read",
            "to_state": "form_open",
            "action": {"type": "click", "target": "t_open_button"},
            "risk": "safe",
        },
        {
            "from_state": "form_open",
            "to_state": "review_shown",
            "action": {"type": "type", "target": "t_nickname", "value": "{{nickname}}"},
            "risk": "safe",
        },
        {
            "from_state": "review_shown",
            "to_state": "done",
            "action": {"type": "click", "target": "t_commit"},
            "risk": "consequential",
            "verify_effect": {
                "goto": "/members/{{member_number}}",
                "predicate": {"type": "text_present", "value": "{{nickname}}"},
            },
        },
    ],
    "targets": {
        "t_password": [{"kind": "role_name", "role": "textbox", "name": "Password"}],
        "t_member_field": [{"kind": "role_name", "role": "textbox", "name": "Member number"}],
        "t_balance": [{"kind": "right_of_text", "anchor": "Savings balance"}],
        "t_open_button": [{"kind": "role_name", "role": "button", "name": "Open"}],
        "t_nickname": [{"kind": "right_of_text", "anchor": "Nickname"}],
        "t_commit": [{"kind": "role_name", "role": "button", "name": "Continue"}],
        "t_search": [
            {"kind": "role_name", "role": "button", "name": "Search"},
            {"kind": "right_of_text", "anchor": "Member number"},
            {"kind": "picture", "asset": "assets/search_icon.png"},
        ],
    },
    "watchers": [
        {
            "id": "w_not_found",
            "trigger": {"type": "text_present", "value": "No records found"},
            "condition": "business_outcome",
            "outcome": "MEMBER_NOT_FOUND",
            "provenance": "discovery_run_2",
        },
        {
            "id": "w_max_accounts",
            "trigger": {"type": "text_present", "value": "Maximum number of accounts"},
            "condition": "business_outcome",
            "outcome": "MAX_ACCOUNTS_REACHED",
            "provenance": "reviewer:nasi",
        },
    ],
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
        "t_member_field": [{"kind": "role_name", "role": "textbox", "name": "Find member by #"}],
        "t_open_button": [{"kind": "role_name", "role": "button", "name": "Create"}],
        "t_commit": [{"kind": "role_name", "role": "button", "name": "Submit"}],
    },
    "timeouts": {"t_balance": 8000},
}


def artifact_dict():
    return deepcopy(_ARTIFACT)


def overlay_dict():
    return deepcopy(_OVERLAY)
