"""In-memory data for the fake servicing console.

Every member number selects a scenario, so one Artifact can demonstrate every
Condition in the error taxonomy. See docs/error-taxonomy.md.
"""

from copy import deepcopy

# Service accounts. Two roles, mirroring the Role model in docs/CONTEXT.md:
# a read-only login that cannot open accounts at all, and a servicing officer.
USERS = {
    "svc_read": {"password": "read-only-pw", "can_open_accounts": False},
    "svc_officer": {"password": "officer-pw", "can_open_accounts": True},
}

# Supervisors are people. These credentials are deliberately NOT in any Role's
# secrets: no service account holds them, so no automation can clear a flag.
SUPERVISORS = {
    "sup_ramirez": "4821",
    "sup_okafor": "7390",
}

SCENARIO_NORMAL = "normal"
SCENARIO_NOT_FOUND = "not_found"
SCENARIO_NOT_AUTHORIZED = "not_authorized"
SCENARIO_NOTICE = "notice"  # interstitial once, then normal
SCENARIO_TRANSIENT = "transient"  # fails once, then works
SCENARIO_SESSION_EXPIRY = "session_expiry"
SCENARIO_SLOW = "slow"
SCENARIO_MAX_ACCOUNTS = "max_accounts"
SCENARIO_APPROVAL = "approval"          # a screen only a person may clear

# The words the app puts on screen when a member does not exist. A Watcher triggers
# on this exact string, so it is a cross-module contract and lives in one place.
NO_RECORDS = "No records found"

_SEED = {
    "12345": {
        "name": "Jane Q. Public",
        "since": "2014-03-02",
        "savings_balance": "4210.00",
        "checking_balance": "812.34",
        "scenario": SCENARIO_NORMAL,
        "sub_accounts": [],
    },
    "54321": {
        "name": "Marcus Webb",
        "since": "2009-11-20",
        "savings_balance": "1250.00",
        "checking_balance": "2044.10",
        "scenario": SCENARIO_NOTICE,
        "sub_accounts": [],
    },
    "22222": {
        "name": "Restricted Member",
        "since": "2001-01-01",
        "savings_balance": "0.00",
        "checking_balance": "0.00",
        "scenario": SCENARIO_NOT_AUTHORIZED,
        "sub_accounts": [],
    },
    "77777": {
        "name": "Dana Ortiz",
        "since": "2018-06-14",
        "savings_balance": "312.75",
        "checking_balance": "98.00",
        "scenario": SCENARIO_TRANSIENT,
        "sub_accounts": [],
    },
    "88888": {
        "name": "Peter Nowak",
        "since": "2012-09-09",
        "savings_balance": "7788.99",
        "checking_balance": "150.25",
        "scenario": SCENARIO_SESSION_EXPIRY,
        "sub_accounts": [],
    },
    "66666": {
        "name": "Slow Loader",
        "since": "2020-02-02",
        "savings_balance": "44.00",
        "checking_balance": "10.00",
        "scenario": SCENARIO_SLOW,
        "sub_accounts": [],
    },
    "44444": {
        "name": "Iris Holloway",
        "since": "2016-07-19",
        "savings_balance": "2380.40",
        "checking_balance": "60.00",
        "scenario": SCENARIO_APPROVAL,
        "sub_accounts": [],
    },
    "33333": {
        "name": "Full House",
        "since": "2005-05-05",
        "savings_balance": "9000.00",
        "checking_balance": "120.00",
        "scenario": SCENARIO_MAX_ACCOUNTS,
        "sub_accounts": ["SA-1001", "SA-1002", "SA-1003"],
    },
}

MAX_SUB_ACCOUNTS = 3

# Members absent from the table produce "No records found"; 99999 is the one
# used in the demos, and is listed here only so the scenario table is complete.
NOT_FOUND_MEMBER = "99999"


class Store:
    """Mutable run-time state. Reset between demo runs so evidence is repeatable."""

    def __init__(self):
        self.members = deepcopy(_SEED)
        self.seen_once = set()  # scenarios that fire on first visit only
        self.approvals = []     # who cleared which flag, as an audit trail would
        self.next_account_seq = 2000

    def reset(self):
        self.__init__()

    def get(self, member_number):
        return self.members.get(member_number)

    def fire_once(self, scenario, member_number):
        """True the first time this scenario fires for this member, False afterwards.

        The key is built here rather than spelled out at each call site, so clearing
        one cannot drift from setting it.
        """
        key = f"{scenario}:{member_number}"
        if key in self.seen_once:
            return False
        self.seen_once.add(key)
        return True

    def clear(self, scenario, member_number):
        """Mark a scenario as already fired — what a supervisor's sign-off does."""
        self.seen_once.add(f"{scenario}:{member_number}")

    def open_sub_account(self, member_number, account_type, nickname):
        member = self.members[member_number]
        self.next_account_seq += 1
        number = f"SA-{self.next_account_seq}"
        member["sub_accounts"].append(number)
        return number


store = Store()


# Every scenario constant must be reachable, or it is documentation rather than
# behaviour. Two of them used to be neither read nor removed; this is the same rule
# the Artifact lint applies to an Outcome Code no Watcher can produce.
IMPLICIT_SCENARIOS = {
    SCENARIO_NOT_FOUND,     # no member is seeded with it: that IS the condition
}
_tagged = {m["scenario"] for m in _SEED.values()} | IMPLICIT_SCENARIOS
_declared = {v for k, v in dict(globals()).items()
             if k.startswith("SCENARIO_") and isinstance(v, str)}
assert _declared == _tagged, \
    f"scenario constants nothing produces: {sorted(_declared - _tagged)}"
