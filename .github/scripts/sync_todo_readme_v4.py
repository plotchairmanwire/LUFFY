#!/usr/bin/env python3
"""Fix-forward reconciliation of the README Complete TODO List.

Rebuilds ONLY the '### 📝 Complete TODO List' section body:
- keeps every existing bullet for files not changed main..dev (raw bytes kept);
- removes every existing bullet for changed .py files (even malformed ones);
- re-adds fresh bullets scanned from the current dev code;
- sorts all bullets by (file path, line number).
Everything outside the section body is left untouched.
"""
import os
import re
import subprocess
import sys

HEADER = "### 📝 Complete TODO List"
MAIN_REF = "origin/main"
DEV_REF = "origin/dev"
BULLET_RE = re.compile(r"^- \[ \] \*\*(?P<path>[^*]+?):(?P<line>\d+)\*\*")
FULL_RE = re.compile(
    r"^- \[ \] \*\*(?P<path>[^*]+?):(?P<line>\d+)\*\* - (?P<msg>.*?)\s*$"
)


def git(*args):
    res = subprocess.run(["git", *args], capture_output=True, text=True)
    if res.returncode != 0:
        print("git error:", args, res.stderr)
        sys.exit(1)
    return res.stdout


def scan_todos(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    out = []
    for lineno, raw in enumerate(lines, 1):
        s = raw.strip()
        if not s.startswith("#") or "TODO" not in s:
            continue
        body = s[1:].strip()
        rest = body[body.find("TODO") + 4:].strip()
        msg = rest if rest.startswith("(") else rest.lstrip(":").strip()
        out.append((lineno, msg))
    return out


def main():
    root = git("rev-parse", "--show-toplevel").strip()
    os.chdir(root)
    subprocess.run(["git", "fetch", "origin", "main", "dev"],
                   capture_output=True, text=True)

    changed = set()
    for p in git("diff", "--name-only", MAIN_REF, DEV_REF).split():
        if p.endswith(".py") and not p.startswith(".github/"):
            changed.add(p)
    print("Changed source files:", sorted(changed))

    raw_bytes = open("README.md", "rb").read()
    eol = "\r\n" if raw_bytes.count(b"\r\n") > 0 else "\n"
    text = raw_bytes.decode("utf-8")
    lines = text.splitlines()

    h = next(i for i, ln in enumerate(lines) if ln.strip() == HEADER)
    t = next(j for j in range(h + 1, len(lines))
             if lines[j].lstrip().startswith("## "))

    head = lines[:h + 1]
    tail = lines[t:]
    body = lines[h + 1:t]

    unchanged = []   # (path, line, raw_line_no_eol)
    unmatched_removed = []
    for ln in body:
        m = BULLET_RE.match(ln)
        if not m:
            continue
        path, line = m.group("path"), int(m.group("line"))
        if path in changed:
            if not FULL_RE.match(ln):
                unmatched_removed.append(ln[:120])
            continue
        unchanged.append((path, line, ln.rstrip("\r")))

    print("Unchanged-file bullets kept:", len(unchanged))
    print("Malformed/changed bullets dropped:", len(unmatched_removed))
    for u in unmatched_removed:
        print("  DROP:", u)

    fresh = []
    for path in sorted(changed):
        todos = scan_todos(path)
        print(f"{path}: {len(todos)} TODOs")
        for line, msg in todos:
            print(f"   @{line}: {msg[:100]}")
            fresh.append((path, line,
                          f"- [ ] **{path}:{line}** - {msg}"))

    combined = [(p, l, raw) for p, l, raw in unchanged] + fresh
    combined.sort(key=lambda e: (e[0], e[1]))
    bullets = [raw for _, _, raw in combined]
    print("Final section bullets:", len(bullets))

    new_lines = head + [""] + bullets + [""] + tail
    new_text = eol.join(new_lines)
    if text.endswith(("\n", "\r")):
        if not new_text.endswith(eol):
            new_text += eol

    if new_text == text:
        print("README unchanged.")
        return

    with open("README.md", "w", encoding="utf-8", newline="") as fh:
        fh.write(new_text)
    print("README.md rewritten.")


if __name__ == "__main__":
    main()
