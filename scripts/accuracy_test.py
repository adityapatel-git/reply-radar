"""Accuracy test: compare Reply Radar's "needs a reply" flags with your own judgment.

Demo inboxes (labels are built into data/sample_emails.json):
    python scripts/accuracy_test.py --demo

Real inboxes (Day 2 of the work plan):
    1. python scripts/accuracy_test.py --export labels.csv
       -> runs triage and writes one row per email with an empty `my_judgment` column
    2. Open labels.csv, put y or n in `my_judgment` for every row
    3. python scripts/accuracy_test.py --score labels.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from reply_radar.config import load_config  # noqa: E402
from reply_radar.pipeline import run  # noqa: E402


def report(rows: list[dict]) -> dict:
    """rows: {subject, account, predicted: bool, expected: bool}"""
    tp = sum(r["predicted"] and r["expected"] for r in rows)
    fp = sum(r["predicted"] and not r["expected"] for r in rows)
    fn = sum(not r["predicted"] and r["expected"] for r in rows)
    tn = sum(not r["predicted"] and not r["expected"] for r in rows)
    total = len(rows)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    accuracy = (tp + tn) / total if total else 0.0

    print(f"\nEmails checked:          {total}")
    print(f"Accuracy:                {accuracy:.0%}  ({tp + tn}/{total} decisions match your judgment)")
    print(f"Precision (flags right): {precision:.0%}  ({tp}/{tp + fp} flagged emails really needed a reply)")
    print(f"Recall (caught):         {recall:.0%}  ({tp}/{tp + fn} emails needing a reply were caught)")
    print(f"Missed:                  {fn}")
    print(f"False alarms:            {fp}")
    for label, cond in (("MISSED (needed a reply, not flagged)", lambda r: r["expected"] and not r["predicted"]),
                        ("FALSE ALARM (flagged, didn't need a reply)", lambda r: r["predicted"] and not r["expected"])):
        bad = [r for r in rows if cond(r)]
        if bad:
            print(f"\n{label}:")
            for r in bad:
                print(f"  - [{r['account']}] {r['subject']}")

    per_acc: dict[str, list[dict]] = {}
    for r in rows:
        per_acc.setdefault(r["account"], []).append(r)
    print("\nPer account:")
    for acc, rs in sorted(per_acc.items()):
        ok = sum(r["predicted"] == r["expected"] for r in rs)
        print(f"  {acc:<10} {ok}/{len(rs)} correct")
    return {"accuracy": accuracy, "precision": precision, "recall": recall, "missed": fn,
            "false_alarms": fp, "total": total}


def demo(offline: bool) -> dict:
    cfg = load_config(ROOT / "config.demo.yaml")
    result = run(cfg, offline=offline, skip_drafts=True)
    truth = {e["id"]: e["expected_needs_reply"]
             for e in json.loads((ROOT / "data" / "sample_emails.json").read_text())["emails"]}
    rows = [{"subject": e.subject, "account": e.account,
             "predicted": result.decisions[e.id].needs_reply, "expected": truth[e.id]}
            for e in result.emails]
    print(f"\nTriage engine: {result.stats['engine']}")
    print(f"Duplicate copies removed: {result.stats['duplicates']}")
    return report(rows)


def export(path: Path, config: Path, offline: bool) -> None:
    cfg = load_config(config)
    result = run(cfg, offline=offline, skip_drafts=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "account", "from", "subject", "predicted_needs_reply", "reason", "my_judgment"])
        for e in result.emails:
            d = result.decisions[e.id]
            w.writerow([e.id, e.account, e.sender_email, e.subject, "y" if d.needs_reply else "n", d.reason, ""])
    print(f"\nWrote {len(result.emails)} rows to {path}. Fill in my_judgment with y/n, then run --score {path}")


def score(path: Path) -> dict:
    rows = []
    with path.open() as f:
        for r in csv.DictReader(f):
            j = (r.get("my_judgment") or "").strip().lower()
            if j not in ("y", "n", "yes", "no"):
                continue
            rows.append({"subject": r["subject"], "account": r["account"],
                         "predicted": r["predicted_needs_reply"].strip().lower() == "y",
                         "expected": j.startswith("y")})
    if not rows:
        sys.exit("No rows with my_judgment filled in.")
    return report(rows)


def main() -> None:
    load_dotenv(ROOT / ".env")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--demo", action="store_true", help="score against the labelled sample inboxes")
    g.add_argument("--export", metavar="CSV", help="triage real inboxes and write a labelling sheet")
    g.add_argument("--score", metavar="CSV", help="score a filled-in labelling sheet")
    p.add_argument("--config", default=str(ROOT / "config.yaml"))
    p.add_argument("--offline", action="store_true", help="use keyword rules instead of Claude")
    p.add_argument("--json", metavar="FILE", help="also save the numbers as JSON (handy for the pitch)")
    a = p.parse_args()

    if a.demo:
        res = demo(a.offline)
    elif a.export:
        export(Path(a.export), Path(a.config), a.offline)
        return
    else:
        res = score(Path(a.score))
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=2))
        print(f"\nSaved results to {a.json}")


if __name__ == "__main__":
    main()
