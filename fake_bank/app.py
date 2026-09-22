"""A deliberately hostile stand-in for a legacy member-servicing console.

Hostile on purpose (see docs/PRD.md): server-rendered with full page reloads,
nested table layout, no ids or test ids on anything that matters, session-scoped
generated control names, an unlabelled icon button, duplicate "Open" text, the
member panel inside an iframe, and per-member scenarios that exercise every
Condition in the error taxonomy.

    SKIN=bank1 (default) or SKIN=bank2   — the two "tenants" running the same product
    PORT=5001
"""

import os
import random
import time

from flask import (
    Flask,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from . import data
from .data import store

app = Flask(__name__)
app.secret_key = "fake-bank-not-a-real-secret"

SKINS = {
    "bank1": {
        "institution": "First Credit Union",
        "member_field_label": "Member number",
        "search_icon": "search.svg",
        "search_title": "",  # no label at all: the B1 unlabelled control
        "open_button": "Open",
        "commit_button": "Continue",
        "icon_before_field": False,
    },
    "bank2": {
        "institution": "Lakeside Savings",
        "member_field_label": "Find member by #",
        "search_icon": "find.svg",
        "search_title": "",
        "open_button": "Create",
        "commit_button": "Submit",
        "icon_before_field": True,  # icon moves above/before the field
    },
}


def skin():
    return SKINS.get(os.environ.get("SKIN", "bank1"), SKINS["bank1"])


def ctl(name):
    """A session-scoped generated control name, as legacy frameworks emit.

    Changes every session, so anything that records it and replays it later
    breaks — which is the point.
    """
    salt = session.get("ctl_salt")
    if salt is None:
        salt = random.randint(1000, 9999)
        session["ctl_salt"] = salt
    return f"ctl00_{name}_{salt}"


@app.context_processor
def template_globals():
    return {"skin": skin(), "ctl": ctl}


def logged_in():
    return session.get("user") in data.USERS


def can_open_accounts():
    user = data.USERS.get(session.get("user"))
    return bool(user and user["can_open_accounts"])


@app.route("/")
def index():
    if not logged_in():
        return redirect(url_for("login"))
    return redirect(url_for("search"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get(ctl("user"), "")
        password = request.form.get(ctl("pass"), "")
        record = data.USERS.get(user)
        if record and record["password"] == password:
            session["user"] = user
            return redirect(url_for("search"))
        return render_template("login.html", message="Invalid user ID or password.")
    return render_template("login.html", message=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/search", methods=["GET"])
def search():
    if not logged_in():
        return redirect(url_for("login"))
    return render_template("search.html", message=None)


@app.route("/members", methods=["POST"])
def member_lookup():
    """Search submission. Scenarios fire here, before the detail page."""
    if not logged_in():
        return redirect(url_for("login"))

    number = (request.form.get(ctl("member"), "") or "").strip()
    member = store.get(number)

    if member is None:
        return render_template("search.html", message="No records found")

    scenario = member["scenario"]

    if scenario == data.SCENARIO_NOT_AUTHORIZED:
        return render_template("not_authorized.html", number=number)

    if scenario == data.SCENARIO_SESSION_EXPIRY:
        session.clear()
        return render_template("login.html", message="Your session has expired. Please sign in again.")

    if scenario == data.SCENARIO_TRANSIENT and store.fire_once(f"transient:{number}"):
        response = make_response(render_template("app_error.html", transient=True))
        response.status_code = 200  # legacy apps love a 200 with an error page
        return response

    if scenario == data.SCENARIO_NOTICE and store.fire_once(f"notice:{number}"):
        return render_template("notice.html", number=number)

    return redirect(url_for("member_detail", number=number))


@app.route("/members/<number>")
def member_detail(number):
    if not logged_in():
        return redirect(url_for("login"))
    member = store.get(number)
    if member is None:
        return render_template("search.html", message="No records found")
    return render_template("member.html", number=number, member=member)


@app.route("/members/<number>/panel")
def member_panel(number):
    """The balances, inside an iframe, so frame scope matters to any locator."""
    if not logged_in():
        return render_template("frame_expired.html")
    member = store.get(number)
    if member is None:
        return render_template("frame_expired.html")
    if member["scenario"] == data.SCENARIO_SLOW:
        time.sleep(3.0)
    else:
        time.sleep(0.3)
    return render_template("panel.html", number=number, member=member)


@app.route("/members/<number>/subaccounts/new", methods=["GET"])
def subaccount_new(number):
    if not logged_in():
        return redirect(url_for("login"))
    if not can_open_accounts():
        return render_template("not_permitted.html")
    member = store.get(number)
    if member is None:
        return render_template("search.html", message="No records found")
    return render_template("subaccount_new.html", number=number, member=member, message=None)


@app.route("/members/<number>/subaccounts/review", methods=["POST"])
def subaccount_review(number):
    if not logged_in():
        return redirect(url_for("login"))
    if not can_open_accounts():
        return render_template("not_permitted.html")
    member = store.get(number)
    account_type = request.form.get(ctl("acct_type"), "")
    nickname = (request.form.get(ctl("nickname"), "") or "").strip()

    if not nickname:
        return render_template(
            "subaccount_new.html", number=number, member=member,
            message="Nickname is required.",
        )
    if len(nickname) > 20:
        return render_template(
            "subaccount_new.html", number=number, member=member,
            message="Nickname must be 20 characters or fewer.",
        )

    return render_template(
        "subaccount_review.html", number=number, member=member,
        account_type=account_type, nickname=nickname,
    )


@app.route("/members/<number>/subaccounts/commit", methods=["POST"])
def subaccount_commit(number):
    """The Consequential Action: this really creates the account."""
    if not logged_in():
        return redirect(url_for("login"))
    if not can_open_accounts():
        return render_template("not_permitted.html")

    member = store.get(number)
    account_type = request.form.get(ctl("acct_type"), "")
    nickname = request.form.get(ctl("nickname"), "")

    if len(member["sub_accounts"]) >= data.MAX_SUB_ACCOUNTS:
        return render_template(
            "subaccount_review.html", number=number, member=member,
            account_type=account_type, nickname=nickname,
            message=f"Maximum number of accounts ({data.MAX_SUB_ACCOUNTS}) reached for this member.",
        )

    new_number = store.open_sub_account(number, account_type, nickname)
    return render_template(
        "subaccount_done.html", number=number, member=member,
        account_type=account_type, nickname=nickname, new_number=new_number,
    )


@app.route("/admin")
def admin():
    """Exists so policy enforcement has something real to refuse."""
    return render_template("admin.html")


@app.route("/leaky")
def leaky():
    """A member notes field containing an off-site image.

    Nobody clicks anything: rendering the page is enough to send data away. Stands in
    for a prompt-injection or exfiltration attempt planted in member data, and exists
    so route interception has something real to block.
    """
    return render_template("leaky.html")


@app.route("/reset", methods=["GET", "POST"])
def reset():
    store.reset()
    session.clear()
    return {"reset": True}


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 5001)), debug=False)
