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

    lab = sub.add_parser("labelize", help="Convert VERIFIED review files into gold labels")
    lab.add_argument("--goldset", default="goldset/v1")

    cdiff = sub.add_parser("colddiff", help="Residual-error audit: cold labels vs final labels")
    cdiff.add_argument("--goldset", default="goldset/v1")

    frz = sub.add_parser("freeze", help="Freeze the gold set: write immutable MANIFEST.json")
    frz.add_argument("--goldset", default="goldset/v1")
    frz.add_argument("--version", default="v1")

    reg = sub.add_parser("register-root", help="Register the production prompt as the root artifact")
    reg.add_argument("--registry", default="registry")

    lin = sub.add_parser("lineage", help="Print an artifact's ancestry chain")
    lin.add_argument("artifact_id")
    lin.add_argument("--registry", default="registry")

    ev = sub.add_parser("eval", help="Evaluate a prompt artifact on the gold set")
    ev.add_argument("artifact_id")
    ev.add_argument("--goldset", default="goldset/v1")
    ev.add_argument("--registry", default="registry")
    ev.add_argument("--model", default=None, help="Default: production extraction model")
    ev.add_argument("--concurrency", type=int, default=4)

    noise = sub.add_parser("noise", help="Measure the noise band: N cache-disabled runs of one artifact")
    noise.add_argument("artifact_id")
    noise.add_argument("--goldset", default="goldset/v1")
    noise.add_argument("--registry", default="registry")
    noise.add_argument("--model", default=None)
    noise.add_argument("--n", type=int, default=3)
    noise.add_argument("--concurrency", type=int, default=4)

    cmp_ = sub.add_parser("compare", help="Gate verdict: candidate vs incumbent eval results")
    cmp_.add_argument("incumbent_results", help="runs/eval-<id>-<model>/results.json")
    cmp_.add_argument("candidate_results")
    cmp_.add_argument("--noise", required=True, help="runs/noise-<id>-<model>.json")

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
    elif args.command == "labelize":
        _cmd_labelize(args)
    elif args.command == "colddiff":
        _cmd_colddiff(args)
    elif args.command == "freeze":
        _cmd_freeze(args)
    elif args.command == "register-root":
        _cmd_register_root(args)
    elif args.command == "lineage":
        _cmd_lineage(args)
    elif args.command == "eval":
        _cmd_eval(args)
    elif args.command == "noise":
        _cmd_noise(args)
    elif args.command == "compare":
        _cmd_compare(args)


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


def _cmd_labelize(args: argparse.Namespace) -> None:
    from extraction_gym.core.labelize import labelize

    summary = labelize(Path(args.goldset))
    for warning in summary["warnings"]:
        print(f"WARN {warning}")
    print(f"labels written: {len(summary['written'])}, not yet VERIFIED: {len(summary['skipped_not_verified'])}")


def _cmd_colddiff(args: argparse.Namespace) -> None:
    from extraction_gym.core.labelize import colddiff

    audit = colddiff(Path(args.goldset))
    if audit["pending"]:
        print(f"pending (no DONE cold form or no final label yet): {' '.join(audit['pending'])}")
    for page_id, fields in audit["per_page"].items():
        print(f"{page_id}: {', '.join(fields)}")
    rate = audit["residual_error_rate"]
    print(
        f"audit pages: {audit['audit_pages']}, fields compared: {audit['fields_compared']}, "
        f"changed: {audit['fields_changed']}, residual error rate: "
        + (f"{rate:.3f}" if rate is not None else "n/a")
    )


def _cmd_freeze(args: argparse.Namespace) -> None:
    from extraction_gym.core.freeze import FreezeError, freeze

    try:
        manifest = freeze(Path(args.goldset), version=args.version)
    except FreezeError as exc:
        print(f"REFUSED: {exc}")
        sys.exit(1)
    print(
        f"frozen {manifest['version']}: {manifest['page_count']} pages, "
        f"residual error {manifest['residual_label_error']['rate']:.3f}"
    )


def _cmd_register_root(args: argparse.Namespace) -> None:
    from coffee_value_app.extractor import EXTRACTION_SYSTEM_PROMPT

    from extraction_gym.core.registry import PromptRegistry

    artifact = PromptRegistry(Path(args.registry)).register(
        text=EXTRACTION_SYSTEM_PROMPT,
        parent_id=None,
        mutation_note="production prompt: schema v2 + source-language fix (R15)",
        source="human",
    )
    print(f"root artifact: {artifact.artifact_id}")


def _cmd_lineage(args: argparse.Namespace) -> None:
    from extraction_gym.core.registry import PromptRegistry

    for artifact in PromptRegistry(Path(args.registry)).lineage(args.artifact_id):
        print(f"{artifact.artifact_id}  parent={artifact.parent_id or '-'}  [{artifact.source}]  {artifact.mutation_note}")


def _cmd_eval(args: argparse.Namespace) -> None:
    from coffee_value_app.config import load_settings

    from extraction_gym.adapters.coffee.extractor import CoffeeExtractor
    from extraction_gym.core.cache import ExtractionCache
    from extraction_gym.core.registry import PromptRegistry
    from extraction_gym.eval.runner import evaluate_artifact, report_markdown

    registry = PromptRegistry(Path(args.registry))
    artifact = registry.get(args.artifact_id)
    model = args.model or load_settings().extraction_model
    extractor = CoffeeExtractor()
    report = asyncio.run(
        evaluate_artifact(
            Path(args.goldset),
            artifact,
            model=model,
            extract_fn=extractor.extract,
            cache=ExtractionCache(Path(".cache") / "extractions"),
            concurrency=args.concurrency,
        )
    )
    runs_dir = Path("runs") / f"eval-{artifact.artifact_id}-{model}"
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "results.json").write_text(
        __import__("json").dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (runs_dir / "report.md").write_text(report_markdown(report), encoding="utf-8")
    registry.append_ledger(
        {
            "event": "eval",
            "artifact_id": artifact.artifact_id,
            "model": model,
            "goldset": str(args.goldset),
            "pages": report["pages"],
            "composite_mean": report["composite_mean"],
            "usage": report["usage"],
        }
    )
    print(report_markdown(report))
    print(f"written: {runs_dir}/report.md")


def _cmd_noise(args: argparse.Namespace) -> None:
    import json

    from coffee_value_app.config import load_settings

    from extraction_gym.adapters.coffee.extractor import CoffeeExtractor
    from extraction_gym.core.cache import ExtractionCache
    from extraction_gym.core.registry import PromptRegistry
    from extraction_gym.eval.runner import evaluate_artifact
    from extraction_gym.eval.stats import noise_band

    registry = PromptRegistry(Path(args.registry))
    artifact = registry.get(args.artifact_id)
    model = args.model or load_settings().extraction_model
    extractor = CoffeeExtractor()
    cache = ExtractionCache(Path(".cache") / "extractions")
    reports = []
    for i in range(args.n):
        report = asyncio.run(
            evaluate_artifact(
                Path(args.goldset),
                artifact,
                model=model,
                extract_fn=extractor.extract,
                cache=cache,
                concurrency=args.concurrency,
                cache_disabled=True,
                run_tag=f"noise-{i}",
            )
        )
        reports.append(report)
        print(f"run {i + 1}/{args.n}: composite {report['composite_mean']:.4f}")
    band = noise_band(reports)
    out = Path("runs") / f"noise-{artifact.artifact_id}-{model}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(band, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    registry.append_ledger(
        {"event": "noise", "artifact_id": artifact.artifact_id, "model": model,
         "composite_std": band["composite_std"], "runs": args.n}
    )
    print(f"composite std: {band['composite_std']:.5f} (gate threshold 2x = {2 * band['composite_std']:.5f})")
    print(f"written: {out}")


def _cmd_compare(args: argparse.Namespace) -> None:
    import json

    from extraction_gym.eval.stats import compare

    report_a = json.loads(Path(args.incumbent_results).read_text(encoding="utf-8"))
    report_b = json.loads(Path(args.candidate_results).read_text(encoding="utf-8"))
    band = json.loads(Path(args.noise).read_text(encoding="utf-8"))
    result = compare(report_a, report_b, band)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"VERDICT: {result['verdict']}")


def _cmd_verify(args: argparse.Namespace) -> None:
    store = GoldsetStore(Path(args.goldset))
    corrupted = store.verify_checksums()
    manifest_problems = store.verify_manifest()
    if corrupted:
        print(f"CORRUPTED: {', '.join(corrupted)}")
    for problem in manifest_problems:
        print(f"MANIFEST: {problem}")
    if corrupted or manifest_problems:
        sys.exit(1)
    print("all checksums OK")


if __name__ == "__main__":
    main()
