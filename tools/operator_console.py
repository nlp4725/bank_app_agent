"""The Operator's console: a page, not a terminal.

    python -m tools.operator_console          # http://127.0.0.1:5010

Deliberately minimal (the brief allows mocking the console). What is real is the
mechanism underneath: the automation has released the lease, the session it was using
is still open, and pressing a button here is what hands control back.
"""

import json
from pathlib import Path

from flask import Flask, redirect, request, send_file, url_for

app = Flask(__name__)
RUNS = Path("runs")

PAGE = """<!doctype html><html><head><title>Operator console</title><style>
 body{{font-family:-apple-system,Segoe UI,Verdana,sans-serif;background:#eceff1;margin:0}}
 .hdr{{background:#123a5e;color:#fff;padding:12px 18px;font-weight:600}}
 .wrap{{padding:18px;max-width:1000px}}
 .card{{background:#fff;border:1px solid #9aa7b0;padding:16px;margin-bottom:16px}}
 .k{{color:#5c6b76;font-size:12px;text-transform:uppercase;letter-spacing:.04em}}
 .v{{font-size:15px;margin-bottom:10px}}
 .why{{background:#fff6d8;border:1px solid #d9c26a;padding:8px 10px;margin:10px 0}}
 img{{max-width:100%;border:1px solid #c3ccd3;margin-top:10px}}
 button{{font-size:14px;padding:8px 18px;margin-right:10px;border:1px solid #9aa7b0;cursor:pointer}}
 .go{{background:#1f7a3f;color:#fff;border-color:#1f7a3f}} .no{{background:#a33;color:#fff;border-color:#a33}}
 .none{{color:#5c6b76;padding:20px}}
</style></head><body><div class="hdr">Operator console — member servicing automation</div>
<div class="wrap">{body}</div></body></html>"""

CARD = """<div class="card">
  <div class="k">capability</div><div class="v">{capability}</div>
  <div class="k">stopped at</div><div class="v">{state} &nbsp;·&nbsp; {watcher}</div>
  <div class="why"><b>Why it stopped:</b> {reason}<br>
    <b>What to do:</b> {instruction}</div>
  <div class="k">the live session</div><div class="v">{url}</div>
  <form method="post" action="/decide">
    <input type="hidden" name="run" value="{run}">
    <button class="go" name="decision" value="resume">Resume now</button>
    <button class="no" name="decision" value="abort">Abort this run</button>
  </form>
  <img src="/shot/{run}">
</div>"""


STALE_AFTER_S = 30 * 60


def open_requests():
    """Unanswered, and recent. A request nobody is waiting on any more is noise."""
    import time
    for path in sorted(RUNS.glob("*/intervention.json"), key=lambda p: p.stat().st_mtime,
                       reverse=True):
        if (path.parent / "decision.json").exists():
            continue
        if time.time() - path.stat().st_mtime > STALE_AFTER_S:
            continue
        yield path.parent.name, json.loads(path.read_text())


@app.route("/")
def index():
    cards = [CARD.format(run=run, capability=r["capability"], state=r["state"],
                         watcher=r.get("watcher") or "unrecognised screen",
                         reason=r["reason"], url=r["url"],
                         instruction=r.get("instruction") or
                         "Finish this in the browser window that is already open — "
                         "the run continues by itself once the blocking screen is gone.")
             for run, r in open_requests()]
    body = "".join(cards) or '<div class="card none">No interventions waiting.</div>'
    return PAGE.format(body=body)


@app.route("/shot/<run>")
def shot(run):
    request_file = RUNS / run / "intervention.json"
    path = json.loads(request_file.read_text())["screenshot"]
    return send_file(Path(path).resolve())


@app.route("/decide", methods=["POST"])
def decide():
    run = request.form["run"]
    (RUNS / run / "decision.json").write_text(json.dumps(
        {"decision": request.form["decision"], "operator": "operator:console"}))
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(port=5010)
