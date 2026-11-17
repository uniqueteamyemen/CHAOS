#!/usr/bin/env python3
"""Fail when a proposed Git diff touches the frozen experiments/ archive."""

from __future__ import annotations

import argparse
import subprocess
import sys


def changed_paths(base: str, head: str, triple_dot: bool) -> list[tuple[str, list[str]]]:
    if not base or not head:
        raise ValueError("both --base and --head are required")

    revisions = [f"{base}...{head}"] if triple_dot else [base, head]

    command = [
        "git",
        "diff",
        "--name-status",
        "--find-renames",
        *revisions,
        "--",
        "experiments/",
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "git diff failed; refusing to treat an unverifiable diff as clean: "
            + completed.stderr.strip()
        )

    parsed: list[tuple[str, list[str]]] = []
    for line in completed.stdout.splitlines():
        fields = line.split("\t")
        if not fields:
            continue
        status = fields[0]
        paths = fields[1:]
        parsed.append((status, paths))
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, help="Base commit SHA")
    parser.add_argument("--head", required=True, help="Head commit SHA")
    parser.add_argument(
        "--triple-dot",
        action="store_true",
        help="Compare merge-base(base, head) to head (pull-request semantics)",
    )
    args = parser.parse_args()

    try:
        touched = changed_paths(args.base, args.head, args.triple_dot)
    except Exception as exc:  # fail closed
        print(f"IMMUTABILITY CHECK ERROR: {exc}", file=sys.stderr)
        return 2

    if touched:
        print("IMMUTABILITY VIOLATION: experiments/ is frozen.", file=sys.stderr)
        for status, paths in touched:
            print(f"{status}\t" + "\t".join(paths), file=sys.stderr)
        return 1

    print("PASS: no changed path touches experiments/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
