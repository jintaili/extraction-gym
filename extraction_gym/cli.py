from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from extraction_gym.core.goldset import GoldsetStore


def main() -> None:
    parser = argparse.ArgumentParser(prog="gym", description="extraction-gym CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snapshot", help="Fetch a URL and store its normalized page text in a gold set")
    snap.add_argument("url")
    snap.add_argument("--stratum", action="append", default=[], help="Stratum tag; repeatable")
    snap.add_argument("--goldset", default="goldset/v1", help="Gold set directory (default goldset/v1)")
    snap.add_argument("--force", action="store_true", help="Overwrite an existing snapshot (pre-freeze only)")

    verify = sub.add_parser("verify", help="Verify gold set page checksums")
    verify.add_argument("--goldset", default="goldset/v1")

    pre = sub.add_parser("prelabel", help="Run two extractors over all snapshots; write review files")
    pre.add_argument("--goldset", default="goldset/v1")
    pre.add_argument("--models", nargs=2, metavar=("UNDER_TEST", "FRONTIER"), required=True)
    pre.add_argument("--limit", type=int, default=None)
    pre.add_argument("--concurrency", type=int, default=4)

    cold = sub.add_parser("coldforms", help="Write blank cold-label forms for the audit subset")
    cold.add_argument("--goldset", default="goldset/v1")
    cold.add_argument("--seed", type=int, default=20260705)
    cold.add_argument("--count", type=int, default=10)

    check = sub.add_parser("checkforms", help="Validate filled cold-label forms")
    check.add_argument("--goldset", default="goldset/v1")

    args = parser.parse_args()
    if args.command == "snapshot":
        _cmd_snapshot(args)
    elif args.command == "verify":
        _cmd_verify(args)
    elif args.command == "prelabel":
        _cmd_prelabel(args)
    elif args.command == "coldforms":
        _cmd_coldforms(args)
    elif args.command == "checkforms":
        _cmd_checkforms(args)


def _cmd_snapshot(args: argparse.Namespace) -> None:
    from extraction_gym.adapters.coffee.fetch_snapshot import fetch_normalized_page

    snapshot = asyncio.run(fetch_normalized_page(args.url))
    store = GoldsetStore(Path(args.goldset))
    stored = store.store_snapshot(
        url=snapshot.url,
        final_url=snapshot.final_url,
        fetched_at=snapshot.fetched_at,
        text=snapshot.text,
        strata=args.stratum,
        force=args.force,
    )
    action = "stored" if stored.created else "exists (strata merged)"
    print(f"{stored.page_id}  {action}  strata={','.join(stored.strata) or '-'}  chars={stored.chars}")


def _cmd_prelabel(args: argparse.Namespace) -> None:
    from extraction_gym.core.prelabel import prelabel_goldset

    summary = asyncio.run(
        prelabel_goldset(
            Path(args.goldset), models=list(args.models), concurrency=args.concurrency, limit=args.limit
        )
    )
    for line in summary["lines"]:
        print(line)
    print(f"pages: {summary['pages']}")
    for model, t in summary["totals"].items():
        print(f"{model}: {t['api_calls']} calls, {t['input_tokens']} in / {t['output_tokens']} out tokens")


def _cmd_coldforms(args: argparse.Namespace) -> None:
    from extraction_gym.core.coldforms import write_cold_forms

    written = write_cold_forms(Path(args.goldset), seed=args.seed, count=args.count)
    for page_id in written:
        print(f"{args.goldset}/coldlabels/{page_id}.cold.yaml")
    print(f"forms written: {len(written)}")


def _cmd_checkforms(args: argparse.Namespace) -> None:
    from extraction_gym.core.checkforms import check_all

    results = check_all(Path(args.goldset))
    bad = 0
    for name, problems in results.items():
        if problems:
            bad += 1
            print(f"{name}:")
            for p in problems:
                print(f"  - {p}")
    print(f"forms: {len(results)}, with problems: {bad}")
    if bad:
        sys.exit(1)


def _cmd_verify(args: argparse.Namespace) -> None:
    corrupted = GoldsetStore(Path(args.goldset)).verify_checksums()
    if corrupted:
        print(f"CORRUPTED: {', '.join(corrupted)}")
        sys.exit(1)
    print("all checksums OK")


if __name__ == "__main__":
    main()
