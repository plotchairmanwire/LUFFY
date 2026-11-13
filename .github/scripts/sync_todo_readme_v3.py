#!/usr/bin/env python3
"""Synchronize the README 'Complete TODO List' section with the Python code.

Rules:
- The existing README list is the baseline.
- Only TODO additions, removals and line-number updates introduced by the
  main..dev changes are applied; files untouched by main..dev keep their
  original README bullet bytes verbatim.
- Entries are ordered by file path (lexicographic) and then by line number.
- The section title line is never modified.
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
    """Return [(line, message)] for TODO comment lines in a .py file."""
    if ref is not None:
        res = subprocess.run(["git", "show", f"{ref}:{path}"],
                             capture_output=True, text=True)
        if res.returncode != 0:
            return []
        lines = res.stdout.splitlines()
    else:
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    out = []
    for lineno, raw in enumerate(lines, 1):
        stripped = raw.strip()
        if not stripped.startswith("#"):
            continue
        if "TODO" not in stripped:
            continue
        body = stripped[1:].strip()
        idx = body.find("TODO")
        rest = body[idx + 4:].strip()
        if rest.startswith("("):
            msg = rest
        else:
            msg = rest.lstrip(":").strip()
        out.append((lineno, msg))
    return out


def main():
    root = git("rev-parse", "--show-toplevel").strip()
    os.chdir(root)
    subprocess.run(["git", "fetch", "origin", "main", "dev"],
                   capture_output=True, text=True)

    changed = []
    for p in git("diff", "--name-only", MAIN_REF, DEV_REF).split():
        if not p.endswith(".py"):
            continue
        if p.startswith(".github/"):
            continue
        changed.append(p)
    print("Changed python source files main..dev:", changed)

    with open("README.md", encoding="utf-8") as f:
        readme = f.read()
    lines = readme.splitlines(keepends=True)

    h = next(i for i, ln in enumerate(lines) if ln.strip() == HEADER)
    end = next(j for j in range(h + 1, len(lines))
               if lines[j].lstrip().startswith("## "))

    region = lines[h + 1:end]
    entry_idx = []
    records = []
    for k, ln in enumerate(region):
        m = ENTRY_RE.match(ln.rstrip("\n"))
        if m:
            entry_idx.append(k)
            records.append({
                "path": m.group("path"),
                "line": int(m.group("line")),
                "msg": m.group("msg"),
                "raw": ln,
            })

    first, last = entry_idx[0], entry_idx[-1]
    prefix = region[:first]
    suffix = region[last + 1:]
    entry_positions = set(entry_idx)
    middle_extra = [ln for k, ln in enumerate(region[first:last + 1])
                     if k not in entry_positions]
    if middle_extra:
        prefix = prefix + middle_extra

    print("Baseline README TODO entries parsed:", len(records))

    baseline_keys = [(r["path"], r["line"], r["msg"]) for r in records]
    if baseline_keys == sorted(baseline_keys):
        print("Baseline ordering check: sorted OK")
    else:
        print("WARNING: baseline entry order differs from sorted order")

    changed_set = set(changed)
    kept = [r for r in records if r["path"] not in changed_set]

    new_records = []
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
            removed.extend([msg] * max(0, cnt - cur_msgs.get(msg, 0)))
        added = []
        for msg, cnt in cur_msgs.items():
            added.extend([msg] * max(0, cnt - main_msgs.get(msg, 0)))
        print(f"\n== {path}")
        print(f"   main TODOs: {len(main_todos)}  dev TODOs: {len(current)}")
        for r in removed:
            print("   REMOVED (done):", r[:100])
        for a in added:
            print("   ADDED (new):", a[:100])
        for line, msg in current:
            print(f"   @{line}: {msg[:100]}")
        new_records.extend(
            {"path": path, "line": line, "msg": msg, "raw": None}
            for line, msg in current
        )

    combined = kept + new_records
    combined.sort(key=lambda r: (r["path"], r["line"], r["msg"]))
    print("\nNew total entries:", len(combined),
          "(baseline", len(records), ")")

    final_lines = []
    for r in combined:
        if r["raw"] is not None:
            final_lines.append(r["raw"])
        else:
            final_lines.append(
                f"- [ ] **{r['path']}:{r['line']}** - {r['msg']}\n")

    new_region = prefix + final_lines + suffix
    new_readme = "".join(lines[:h + 1]) + "".join(new_region) + "".join(lines[end:])

    if new_readme == readme:
        print("README unchanged; nothing to commit.")
        return

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(new_readme)
    print("README.md updated.")


if __name__ == "__main__":
    main()
