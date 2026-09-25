"""The draft as a walk-through: one block per step, everything about that step in it —
where we are and how we know (checkpoint), what we do, on which target and how it is
found, where we land. What the Reviewer reads before being asked anything."""


def target_words(draft: dict, name: str) -> str:
    """A Target's ladder in words: how the control is found, rung by rung."""
    tg = draft["targets"][name]
    words = []
    for r in tg["rungs"]:
        if r["kind"] == "role_name":
            words.append(f"the {r['role']} named \"{r['name']}\"")
        elif r["kind"] == "label_anchor":
            what = r.get("role") or "control"
            rel = {"right_of": "right of", "below": "below", "nearest": "nearest"}.get(
                r.get("relation", "nearest"), r.get("relation"))
            words.append(f"the {what} {rel} the caption \"{r['anchor']}\"")
        else:
            words.append("its picture")
    frame = f", inside frame {tg['frame']['url_contains']}" if tg.get("frame") else ""
    return f"{words[0]}{frame}" + (f"   (fallback: {', '.join(words[1:])})" if len(words) > 1 else "")


def checkpoint_words(draft: dict, state_id: str) -> str:
    st = next((s for s in draft["states"] if s["id"] == state_id), None)
    cp = (st or {}).get("checkpoint")
    if not cp:
        return "no checkpoint (terminal)" if st and st.get("terminal") else "no checkpoint"
    if cp["type"] == "element_present":
        return f"target {cp['target']} is on screen"
    if cp["type"] == "text_present":
        return f"the text \"{cp['value']}\" is on screen"
    if cp["type"] == "url_matches":
        return f"the address matches {cp['pattern']}"
    if cp["type"] == "field_value":
        return (f"field {cp['target']} holds a value" if cp.get("non_empty")
                else f"field {cp['target']} reads {cp.get('equals')!r}")
    return f"{cp['type']} holds"


def show_draft(draft: dict, suggestions: list[str]) -> str:
    c = draft["capability"]
    lines = [f"  {c['id']} {c['version']}   role {c['role']}   status {c['status']}",
             f"  {len(draft['states'])} states, {len(draft['transitions'])} steps, "
             f"{len(draft['watchers'])} watchers"]
    here = None
    for n, t in enumerate(draft["transitions"], 1):
        a = t["action"]
        lines.append("")
        at = f"  STEP {n:<2d}  at {t['from_state']}"
        if t["from_state"] != here:
            at += f"      checkpoint: {checkpoint_words(draft, t['from_state'])}"
        lines.append(at)
        verb = {"type": "type", "click": "click", "select": "select", "read": "read"}[a["type"]]
        if a["type"] == "type":
            value = f"<secret {a['value_ref']}>" if a.get("value_ref") else repr(a.get("value"))
            lines.append(f"           {verb:6s} {value}")
            lines.append(f"           into   target {a['target']}  =  {target_words(draft, a['target'])}")
        elif a["type"] == "select":
            lines.append(f"           {verb:6s} {a.get('value')!r}")
            lines.append(f"           in     target {a['target']}  =  {target_words(draft, a['target'])}")
        elif a["type"] == "read":
            lines.append(f"           {verb:6s} target {a['target']}  =  {target_words(draft, a['target'])}")
            lines.append(f"           into   output {a['into']}")
        else:
            lines.append(f"           {verb:6s} target {a['target']}  =  {target_words(draft, a['target'])}")
        if t["to_state"] != t["from_state"]:
            lines.append(f"           then   {t['to_state']}      checkpoint: {checkpoint_words(draft, t['to_state'])}")
        else:
            lines.append(f"           then   still {t['to_state']}")
        st = next((s for s in draft["states"] if s["id"] == t["to_state"]), {})
        if st.get("terminal") and n == len(draft["transitions"]):
            lines.append(f"           done   {t['to_state']} is terminal: SUCCEEDED")
        if t["risk"] == "consequential":
            lines.append("           risk   CONSEQUENTIAL  <- you decide: does this click commit anything?")
        if t.get("verify_effect"):
            lines.append(f"           verify open {t['verify_effect']['goto']}, "
                         f"expect the text {t['verify_effect']['predicate'].get('value')!r}")
        here = t["to_state"]

    lines.append("")
    lines.append("  WATCHERS   if a checkpoint fails, which screen is it?")
    if draft["watchers"]:
        for w in draft["watchers"]:
            tail = (f"outcome {w['outcome']}" if w.get("outcome")
                    else f"click {w['recovery']['target']}" if w.get("recovery") else "")
            lines.append(f"           {w['id']:22s} text \"{w['trigger'].get('value')}\"  ->  {w['condition']}  {tail}")
    else:
        lines.append("           none yet  <- the next questions add them")

    if suggestions:
        lines.append("")
        lines.append("  the Recorder could not decide:")
        lines += [f"    - {s}" for s in suggestions]
    return "\n".join(lines)
