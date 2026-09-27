"""Command-line entry point for `ic`."""

import argparse
import sys
from pathlib import Path

from . import config, spec
from .llm import list_models
from .unit import load_unit

PLACEHOLDER_STAGES = ["check", "impl", "verify"]


def _load_config(root_arg: Path | None) -> config.Config:
    root = root_arg.resolve() if root_arg else config.find_root(Path.cwd())
    if root is None or not (root / config.CONFIG_NAME).is_file():
        where = root_arg or Path.cwd()
        raise FileNotFoundError(f"no {config.CONFIG_NAME} found at or above {where}")
    return config.load(root)


def cmd_endpoints(cfg: config.Config, args) -> int:
    """List configured endpoints and check each is reachable with its model."""
    for name, ep in cfg.endpoints.items():
        try:
            models = list_models(ep)
            status = "ok" if ep.model in models else f"reachable, but model not found"
        except RuntimeError as e:
            status = str(e)
        print(f"{name:14} {ep.model:18} {ep.url:28} {status}")
    return 0


def cmd_spec(cfg: config.Config, args) -> int:
    unit = load_unit(cfg.root, args.unit)
    endpoint = cfg.endpoint_for("spec", args.endpoint)
    return spec.run(cfg, unit, endpoint, dry_run=args.dry_run)


def cmd_placeholder(cfg: config.Config, args) -> int:
    unit = load_unit(cfg.root, args.unit)
    print(f"{args.stage} {unit.name}: not implemented yet")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ic", description="IntentCompiler")
    parser.add_argument("--root", type=Path, default=None,
                        help="project root containing ic.toml (default: search upward)")
    sub = parser.add_subparsers(dest="stage", required=True)

    p = sub.add_parser("endpoints", help="list endpoints and check they respond")
    p.set_defaults(func=cmd_endpoints)

    p = sub.add_parser("spec", help="draft spec.md from intent.md")
    p.add_argument("unit")
    p.add_argument("-e", "--endpoint", help="endpoint name from ic.toml")
    p.add_argument("-n", "--dry-run", action="store_true",
                   help="print the assembled prompt without calling the model")
    p.set_defaults(func=cmd_spec)

    for stage in PLACEHOLDER_STAGES:
        p = sub.add_parser(stage, help=f"{stage} stage (not implemented yet)")
        p.add_argument("unit")
        p.set_defaults(func=cmd_placeholder)

    args = parser.parse_args(argv)
    try:
        cfg = _load_config(args.root)
        return args.func(cfg, args)
    except (FileNotFoundError, KeyError, ValueError, RuntimeError) as e:
        msg = e.args[0] if isinstance(e, KeyError) and e.args else e
        print(f"error: {msg}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())

    
