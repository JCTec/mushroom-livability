"""Mushroom Livability - entry point.

    python main.py              fetch data if needed, then open the web app
    python main.py pipeline     fetch + score + write results and paper fragments
    python main.py serve        only start the web app
    python main.py check        live smoke test of every data source
    python main.py paper        regenerate LaTeX fragments from saved results
    python main.py site         write a static copy of the web app (GitHub Pages)

Add --demo to pipeline/serve/run/paper to use clearly-labelled SYNTHETIC
data (no network needed). Run `python main.py <command> --help` for options.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import threading
import webbrowser

from src.settings import Paths, Settings


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--demo", action="store_true",
                        help="use SYNTHETIC placeholder data (offline; never mixed with real results)")


def _add_pipeline(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--only", default="",
                        help="comma-separated location ids for a quick partial run, e.g. paris,amsterdam")
    parser.add_argument("--clear-cache", action="store_true",
                        help="delete cached API responses first (forces fresh downloads)")


def _add_serve(parser: argparse.ArgumentParser, settings: Settings) -> None:
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser window")


def build_parser(settings: Settings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="pipeline (if no results yet) + web app [default]")
    _add_common(run), _add_pipeline(run), _add_serve(run, settings)
    run.add_argument("--refresh", action="store_true", help="re-run the pipeline even if results exist")

    pipeline = sub.add_parser("pipeline", help="fetch, score, write results and paper fragments")
    _add_common(pipeline), _add_pipeline(pipeline)

    serve = sub.add_parser("serve", help="start the web app on existing results")
    _add_common(serve), _add_serve(serve, settings)

    check = sub.add_parser("check", help="live smoke test of every data source")
    check.add_argument("--location", default="paris", help="location id to test with")

    paper = sub.add_parser("paper", help="regenerate LaTeX fragments from saved results")
    _add_common(paper)

    site = sub.add_parser("site", help="write a static copy of the web app (e.g. for GitHub Pages)")
    _add_common(site)
    site.add_argument("--out", default="site", help="output directory (replaced)")
    return parser


def cmd_pipeline(args, settings: Settings, paths: Paths) -> int:
    from src.pipeline import run_pipeline

    if getattr(args, "clear_cache", False) and paths.cache_dir.exists():
        for child in paths.cache_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
        print("Cache cleared.")
    only = [item for item in args.only.split(",") if item.strip()] if getattr(args, "only", "") else None
    results = run_pipeline(settings, paths, synthetic=args.demo, only=only)
    return 0 if any(loc["scored"] for loc in results["locations"]) else 1


def cmd_serve(args, settings: Settings, paths: Paths) -> int:
    from src.app.server import create_app

    results_file = paths.results_file(args.demo)
    if not results_file.exists():
        print(f"No results at {results_file}. Run `python main.py pipeline{' --demo' if args.demo else ''}` first.")
        return 1
    url = f"http://{args.host}:{args.port}"
    print(f"Mushroom Livability is running at {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    create_app(results_file).run(host=args.host, port=args.port, debug=False, use_reloader=False)
    return 0


def cmd_run(args, settings: Settings, paths: Paths) -> int:
    if args.refresh or args.only or args.clear_cache or not paths.results_file(args.demo).exists():
        code = cmd_pipeline(args, settings, paths)
        if code != 0:
            print("The pipeline produced no scored location; not starting the web app.")
            return code
    return cmd_serve(args, settings, paths)


def cmd_check(args, settings: Settings, paths: Paths) -> int:
    from src.diagnostics import run_checks

    return 0 if run_checks(settings, paths, args.location) else 1


def cmd_paper(args, settings: Settings, paths: Paths) -> int:
    from src.reporting import latex
    from src.reporting.store import load_results

    results = load_results(paths.results_file(args.demo))
    if results is None:
        print("No results found. Run the pipeline first.")
        return 1
    for path in latex.write_fragments(results, paths.paper_generated_dir):
        print(f"wrote {path}")
    print("Now build the PDF:  cd paper && latexmk -pdf paper.tex   (or run pdflatex twice)")
    return 0


def cmd_site(args, settings: Settings, paths: Paths) -> int:
    from src.app.static_site import export_site

    results_file = paths.results_file(args.demo)
    if not results_file.exists():
        print(f"No results at {results_file}. Run `python main.py pipeline{' --demo' if args.demo else ''}` first.")
        return 1
    files = export_site(results_file, args.out)
    print(f"Static site written to {args.out}/ ({len(files)} files). Serve that folder as-is.")
    return 0


COMMANDS = {"run": cmd_run, "pipeline": cmd_pipeline, "serve": cmd_serve, "check": cmd_check, "paper": cmd_paper,
            "site": cmd_site}


def main(argv=None) -> int:
    settings, paths = Settings(), Paths()
    parser = build_parser(settings)
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-") and argv[0] not in ("-h", "--help"):
        argv = ["run"] + argv  # `python main.py` and `python main.py --demo` mean `run`
    args = parser.parse_args(argv)
    return COMMANDS[args.command](args, settings, paths)


if __name__ == "__main__":
    sys.exit(main())
