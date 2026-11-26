"""Command line entry point.

    python -m reply_radar --demo            # sample inboxes, no accounts needed
    python -m reply_radar                   # real accounts from config.yaml
    python -m reply_radar --offline         # force keyword rules instead of Claude
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from .config import load_config
from .digest import render_html, render_markdown
from .pipeline import run

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    load_dotenv(ROOT / ".env")
    p = argparse.ArgumentParser(prog="reply_radar", description="One digest of who's waiting on you.")
    p.add_argument("--demo", action="store_true", help="use the sample inboxes in data/ (config.demo.yaml)")
    p.add_argument("--config", default=None, help="config file (default: config.yaml)")
    p.add_argument("--offline", action="store_true", help="don't call Claude; use keyword rules")
    p.add_argument("--no-drafts", action="store_true", help="skip drafting replies")
    p.add_argument("--no-save", action="store_true", help="print only; don't write the HTML digest")
    args = p.parse_args(argv)

    cfg_path = Path(args.config) if args.config else ROOT / ("config.demo.yaml" if args.demo else "config.yaml")
    if not cfg_path.exists():
        print(f"Config not found: {cfg_path}\nCopy config.example.yaml to config.yaml and fill it in, "
              f"or run with --demo.", file=sys.stderr)
        return 2
    cfg = load_config(cfg_path)

    print(f"Reply Radar: reading {len(cfg.accounts)} accounts (read-only)")
    result = run(cfg, offline=args.offline, skip_drafts=args.no_drafts)
    print()
    print(render_markdown(result.items, result.stats))

    if not args.no_save:
        out_dir = ROOT / cfg.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "digest.html"
        out.write_text(render_html(result.items, result.stats))
        print(f"HTML digest written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
