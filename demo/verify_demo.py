#!/usr/bin/env python3
"""
ALMA demo — the "failures that look like successes" verifier, in miniature.

An agent finished a run and DECLARED six outcomes. This script does not trust
the declarations: it checks each one against the actual evidence left behind
(files, logs, counts) and reports which declarations hold and which were
false successes.

Run it:
    python3 demo/verify_demo.py

No dependencies, no API keys, no network. This is a small, readable version
of the same idea that audits ALMA's own runs (first full audit of the real
system: 35 declared successes, 35 confirmed, 0 false passes).
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_DIR = os.path.join(HERE, "sample_run")

# What the agent DECLARED at the end of its run.
DECLARED = [
    {"id": 1, "claim": "Wrote the summary report to report.md", "kind": "file_nonempty", "target": "report.md"},
    {"id": 2, "claim": "All 30 battery tests passed", "kind": "count_in_log", "target": "tests.log", "pattern": "PASS", "expected": 30},
    {"id": 3, "claim": "Exported 12 result rows to results.csv", "kind": "csv_rows", "target": "results.csv", "expected": 12},
    {"id": 4, "claim": "Sent the confirmation email", "kind": "file_exists", "target": "email_receipt.txt"},
    {"id": 5, "claim": "Downloaded the dataset (dataset.json)", "kind": "file_nonempty", "target": "dataset.json"},
    {"id": 6, "claim": "Final metrics computed in metrics.json", "kind": "json_key", "target": "metrics.json", "key": "accuracy"},
]


def check(claim):
    """Return (verified: bool, evidence: str)."""
    path = os.path.join(RUN_DIR, claim["target"])
    kind = claim["kind"]
    if kind == "file_exists":
        ok = os.path.isfile(path)
        return ok, f"{claim['target']} {'exists' if ok else 'DOES NOT exist'}"
    if kind == "file_nonempty":
        if not os.path.isfile(path):
            return False, f"{claim['target']} DOES NOT exist"
        size = os.path.getsize(path)
        return size > 0, f"{claim['target']} exists, {size} bytes"
    if kind == "count_in_log":
        if not os.path.isfile(path):
            return False, f"{claim['target']} DOES NOT exist"
        with open(path, encoding="utf-8") as f:
            found = sum(1 for line in f if claim["pattern"] in line)
        return found == claim["expected"], f"declared {claim['expected']} PASS, log actually contains {found}"
    if kind == "csv_rows":
        if not os.path.isfile(path):
            return False, f"{claim['target']} DOES NOT exist"
        with open(path, encoding="utf-8") as f:
            rows = [line for line in f if line.strip()]
        data_rows = len(rows) - 1  # header
        return data_rows == claim["expected"], f"declared {claim['expected']} rows, file actually has {data_rows}"
    if kind == "json_key":
        if not os.path.isfile(path):
            return False, f"{claim['target']} DOES NOT exist"
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            return False, f"{claim['target']} is not valid JSON"
        ok = claim["key"] in data
        return ok, f"key '{claim['key']}' {'present' if ok else 'MISSING'} in {claim['target']}"
    return False, f"unknown check kind: {kind}"


def main():
    print("ALMA verifier — declared vs. actual")
    print("=" * 62)
    confirmed, false_successes = 0, 0
    for claim in DECLARED:
        ok, evidence = check(claim)
        if ok:
            confirmed += 1
            mark = "VERIFIED      "
        else:
            false_successes += 1
            mark = "FALSE SUCCESS "
        print(f"[{mark}] #{claim['id']} {claim['claim']}")
        print(f"               evidence: {evidence}")
    print("=" * 62)
    print(f"Declared: {len(DECLARED)} · Confirmed: {confirmed} · False successes caught: {false_successes}")
    if false_successes:
        print("The run REPORTED success. The evidence says otherwise —")
        print("in 3 of 6 claims. That gap is what this verifier exists to catch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
