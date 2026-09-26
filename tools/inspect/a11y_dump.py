"""Print the accessibility view of a page, the way the Discovery LLM would see it.

    python -m tools.inspect.a11y_dump http://localhost:5001/login
    python -m tools.inspect.a11y_dump https://www.saucedemo.com/     # a modern app, for contrast

Prints Playwright's ARIA snapshot (role + accessible name per line), then checks
which interactive controls could be found by role+name alone — rung 1 of a Target
ladder — and which would need a fallback.
"""

import argparse
import re

from playwright.sync_api import sync_playwright

INTERACTIVE = ("button", "textbox", "link", "checkbox", "combobox", "radio", "menuitem", "searchbox")
LINE = re.compile(r'^(\s*)-\s+([a-z]+)(?:\s+"([^"]*)")?')


def dump(url: str, show_tree: bool = True):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(700)
        snapshot = page.locator("body").aria_snapshot()
        print(f"\n=== {url} ===")
        if show_tree:
            print(snapshot)

        print("--- interactive controls: can rung 1 (role + accessible name) find them? ---")
        found = missing = 0
        for line in snapshot.splitlines():
            m = LINE.match(line)
            if not m:
                continue
            _, role, name = m.groups()
            if role not in INTERACTIVE:
                continue
            if name:
                found += 1
                print(f'  {role:10s} "{name}"' + " " * max(0, 26 - len(name)) + "rung 1 works")
            else:
                missing += 1
                print(f"  {role:10s} (no accessible name)        NEEDS A FALLBACK RUNG")
        print(f"\n  {found} findable by role+name, {missing} need a fallback")
        browser.close()


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m tools.inspect.a11y_dump", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("urls", nargs="*", metavar="URL",
                   default=["http://localhost:5001/login"],
                   help="pages to inspect (default http://localhost:5001/login)")
    p.add_argument("--no-tree", action="store_true",
                   help="skip the full ARIA snapshot; print only the rung-1 check")
    args = p.parse_args(argv)
    for url in args.urls:
        dump(url, show_tree=not args.no_tree)


if __name__ == "__main__":
    main()
