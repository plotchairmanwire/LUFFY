#!/usr/bin/env python3
"""Synchronize the README 'Complete TODO List' section with the Python code.

Scope rule: the existing README list is the baseline. Only TODO additions,
removals and line-number updates coming from the main..dev changes are
applied. Files untouched by main..dev keep their baseline entries verbatim.
"""
import os
import re
import subprocess
import sys

HEADER = "### 📝 Complete TODO List"
MAIN_REF = "origin/main"
DEV_REF = "origin/dev"
ENTRY_RE = re.compile(r"^- \[ \] \*\*(?P<path>.+?):(?P<line>\d+)\*\* - (?P<msg>.*)$")


def git(*args):
    res = subprocess.run(["git", *args], capture_output=True, text=True)
    if res.returncode != 0:
        print("git error:", args, res.stderr)
        sys.exit(1)
    return res.stdout


def scan_todos(path, ref=None):
    """Return [(line, message)] for TODO comments in a .py file at ref/worktree."""
    if ref is not None:
        data = git("show", f"{ref}:{path}")
        iterable = enumerate(data.splitlines(), 1)
    else:
        fh = open(path, encoding="utf-8")
        iterable = enumerate(fh, 1)
    out = []
    for lineno, raw in iterable:
        stripped = raw.strip()
        if not stripped.startswith("#"):
            continue
        if "TODO" not in stripped:
            continue
        body = stripped[1:].strip()
        idx = body.find("TODO")
        rest = body[idx + 4:]
        rest_s = rest.strip()
        if rest_s.startswith("("):
            msg = rest_s
        else:
            msg = rest.lstrip(":").strip()
        out.append((lineno, msg))
    if ref is None:
        fh.close()
    return out


def parse_readme_entries(text):
    entries = []
    for raw in text.splitlines():
        m = ENTRY_RE.match(raw)
        if m:
            entries.append((m.group("path"), int(m.group("line")), m.group("msg")))
    return entries


def render_entry(path, line, msg):
    return f"- [ ] **{path}:{line}** - {msg}\n"


def main():
    root = git("rev-parse", "--show-toplevel").strip()
    os.chdir(root)

    # Make sure both remote-tracking branches are available.
    subprocess.run(["git", "fetch", "origin", "main", "dev"], capture_output=True, text=True)

    changed = [
        p for p in git("diff", "--name-only", MAIN_REF, DEV_REF).split()
        if p.endswith(".py")
    ]
    print("Changed python files main..dev:", changed)

    with open("README.md", encoding="utf-8") as f:
        readme = f.read()
    lines = readme.splitlines(keepends=True)

    # Locate section header and the next markdown section.
    h = next(i for i, ln in enumerate(lines) if ln.strip() == HEADER)
    end = next(j for j in range(h + 1, len(lines)) if lines[j].lstrip().startswith("## "))

    block = lines[h + 1:end]
    prefix, suffix = [], []
    seen_entry = False
    for ln in block:
        if ENTRY_RE.match(ln.rstrip("\n")):
            seen_entry = True
        elif not seen_entry:
            prefix.append(ln)
        else:
            suffix.append(ln)

    baseline = parse_readme_entries(readme)
    print("Baseline README TODO entries:", len(baseline))

    # Sanity: baseline must already be sorted by (path, line).
    if baseline != sorted(baseline, key=lambda e: (e[0], e[1])):
        print("WARNING: baseline not sorted; order check failed")
    else:
        print("Baseline ordering check: sorted OK")

    untouched = [(p, l, m) for (p, l, m) in baseline if p not in changed]

    new_groups = []
    for path in sorted(changed):
        current = scan_todos(path)
        main_todos = scan_todos(path, ref=MAIN_REF)
        main_msgs = {}
        for _, msg in main_todos:
            main_msgs[msg] = main_msgs.get(msg, 0) + 1
        cur_msgs = {}
        for _, msg in current:
            cur_msgs[msg] = cur_msgs.get(msg, 0) + 1
        removed = []
        for msg, cnt in main_msgs.items():
            if cnt > cur_msgs.get(msg, 0):
                removed.extend([msg] * (cnt - cur_msgs.get(msg, 0)))
        added = []
        for msg, cnt in cur_msgs.items():
            if cnt > main_msgs.get(msg, 0):
                added.extend([msg] * (cnt - main_msgs.get(msg, 0)))
        print(f"\n== {path}")
        print(f"   main TODOs: {len(main_todos)}  dev TODOs: {len(current)}")
        for r in removed:
            print("   REMOVED (done):", r[:90])
        for a in added:
            print("   ADDED (new):", a[:90])
        for line, msg in current:
            print(f"   @{line}: {msg[:90]}")
        new_groups.extend((path, line, msg) for line, msg in current)

    combined = untouched + new_groups
    combined_sorted = sorted(combined, key=lambda e: (e[0], e[1]))
    print("\nNew total entries:", len(combined_sorted), "(baseline", len(baseline), ")")

    # Verify untouched groups render identically (no unintended edits).
    untouched_rendered = [render_entry(*e) for e in combined_sorted if e[0] not in changed]
    baseline_untouched = [render_entry(*e) for e in baseline if e[0] not in changed]
    if untouched_rendered != baseline_untouched:
        print("ERROR: untouched entries changed under sorting; aborting")
        sys.exit(2)

    new_block = prefix + [render_entry(*e) for e in combined_sorted] + suffix
    new_readme = "".join(lines[:h + 1]) + "".join(new_block) + "".join(lines[end:])

    if new_readme == readme:
        print("README unchanged; nothing to commit.")
        return

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(new_readme)
    print("README.md updated.")


if __name__ == "__main__":
    main()
