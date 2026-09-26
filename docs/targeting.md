# How a Target finds a control

Terms in [CONTEXT.md](./CONTEXT.md). Everything below was measured against the
demo app, not assumed; the commands are in `tools/inspect/a11y_dump.py`.

## The problem, on one screen

The member search page, as written:

```html
<td class="c1">Member number</td>                                  <!-- the words -->
<td class="c1"><input type="text" name="ctl00_member_3928"></td>   <!-- the field  -->
<td class="c1"><button class="iconbtn"><img src="search.svg"></button></td>
```

The same page as the browser's accessibility tree sees it:

```
- heading "Member Search" [level=2]
- table:
  - row "Member number":
    - cell "Member number"        ← plain text in a neighbouring cell
    - cell:
      - textbox                   ← NO accessible name
    - cell:
      - button:                   ← NO accessible name
        - img                     ← no alt text either
```

There is no `<label for>`, no `aria-label`, no placeholder and no id, so the browser
computes **no name** for either control. A human reads left to right and knows what
they are. The machine has two anonymous boxes.

```
┌──────────────────────────────────────────────┐
│  Member number: [____________]  ( 🔍 )        │
│  └─ text ──────┘ └─ textbox ─┘  └ button ┘    │
│     has a name      no name       no name     │
└──────────────────────────────────────────────┘
```

Measured:

```
role_name textbox "Member number"  ->  0 matches
role_name textbox "Password"       ->  0 matches
role_name button  "Search"         ->  0 matches
role_name button  "Sign in"        ->  1 match     (buttons get their name from value=)
```

A modern app (saucedemo.com) for contrast: `textbox "Username"`, `textbox "Password"`,
`button "Login"` — 3 of 3 findable by name. The difference is not our implementation;
it is what the brief means by "legacy enterprise apps essentially never have test IDs".

## The three rungs

Tried in order, and the one that matched is recorded in the run log.

**1. `role_name`** — the accessible name the browser itself computed.
Reads: the accessibility tree. Finds: buttons and links here. Survives: moving,
restyling, re-layout. Breaks: a rename ("Continue" -> "Submit" at another tenant).

**2. `label_anchor`** — find the visible words, then the nearest control of that role
in the given direction. Reads: the accessibility tree plus layout geometry. Finds:
everything with a visible caption, which in this app is every text field and the
balance inside the iframe. Survives: a rename of the *control*. Breaks: the field
moving away from its caption, or the caption itself being renamed.

```
  anchor "Member number"          nearest textbox to its right
  ┌───────────────┐               ┌──────────────┐
  │ Member number │  ──────────►  │              │
  └───────────────┘               └──────────────┘
```

**3. `picture`** — template-match a crop saved at record time. Reads: pixels. Finds:
anything visible, including a control with no text anywhere near it. Survives: renames
and re-layout. Breaks: restyling, theming, a different icon set.

The three break for *different* reasons, which is the point: a rename defeats rung 1
but not rung 2; a move defeats rung 2 but not rung 1 or 3; a re-skin defeats rung 3
but not the others. A single selector has a single failure mode.

Measured on the demo app, with every rung-1 lookup failing:

```
role_name textbox "Password"       -> 0 matches   | label_anchor "Password"      -> found
role_name textbox "Member number"  -> 0 matches   | label_anchor "Member number" -> found
role_name button  "Search"         -> 0 matches   | label_anchor "Member number" -> found (the icon)
balance, inside the iframe         ->             | label_anchor "Savings balance" -> "$4210.00"
```

## What is stored, and what is computed

A Target stores the **relationship**, never a measurement:

```yaml
t_search:
  rungs:
    - {kind: role_name,    role: button, name: "Search"}
    - {kind: label_anchor, anchor: "Member number", role: button, relation: right_of}
    - {kind: picture,      asset: assets/search_icon.png}
```

Pixel distances are recomputed from the live page on every run. Storing "6px to the
right" would break on the first font or padding change.

## Who produces this

```
Discovery LLM   "click element [5]"        — one semantic decision, once
      │          (or a point, for a control the list does not contain)
Our code        performs it, then inspects what was hit:
                  role and accessible name          -> rung 1, when a name exists
                  nearest visible text + direction  -> rung 2, when unambiguous
                  a crop of the element's box       -> rung 3
Artifact        holds those descriptors
Replay          re-resolves them against the live page. No model, no stored coordinates.
```

The model's entire contribution is *which* control. Everything durable is computed by
code from the page.

## Why not a DOM selector rung

`input[type=password]` or an XPath would work in a browser, and the brief permits
DOM-level automation. It was left out because the other three rungs all survive a
change of surface and a DOM rung does not:

| Rung | Browser | Legacy web | Desktop / Citrix |
|---|---|---|---|
| `role_name` | yes | yes | yes — OS accessibility APIs |
| `label_anchor` | yes | yes | yes — geometry plus a11y, or OCR |
| `picture` | yes | yes | yes — often all a virtual desktop offers |
| a DOM selector | yes | yes | **no** |

## Frames

The savings balance is inside an iframe, so it is absent from the main document:

```
frames: ['/members/12345', '/members/12345/panel']
main page contains "Savings balance": False
inside the frame: row "Savings balance  $4210.00"
```

A Target therefore declares its frame, defaulting to the main document:

```yaml
t_balance:
  frame: {url_contains: "/panel"}
  rungs: [{kind: label_anchor, anchor: "Savings balance", relation: right_of}]
```

Searching every frame automatically was rejected: the same caption can appear in two
frames, and silently acting in the wrong one is the "clicked something, nothing
happened" failure this design exists to prevent.
