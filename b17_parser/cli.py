"""Command-line interface for collection, filter inspection, and export."""
from __future__ import annotations

import argparse
import math
import fcntl
import hashlib
from datetime import datetime, timezone
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .catalog import normalize_url, parse_catalog
from .crawler import Collector
from .http import AccessError, FetchError, HttpClient, ManagedClient
from .pacing import AccessGate
from .storage import atomic_json, export_records, read_jsonl


def positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def build_parser():
    parser = argparse.ArgumentParser(description="Collect public B17 profiles into resumable UTF-8 JSONL")
    subs = parser.add_subparsers(dest="command", required=True)
    for name in ("crawl", "profiles", "inspect", "login", "filters"):
        sub = subs.add_parser(name)
        sub.add_argument("--url", required=name not in ("profiles", "login"), action="append" if name == "profiles" else "store")
        sub.add_argument("--delay", type=float, default=15, help="minimum seconds between navigations (default 15)")
        sub.add_argument("--timeout", type=float, default=30)
        sub.add_argument("--jitter", type=float, default=5, help="additional random pause up to N seconds")
        sub.add_argument("--access-state", type=Path, default=Path("work/access-state.json"), help="shared pacing/cooldown file for all runs")
        sub.add_argument("--max-requests", type=positive, default=100, help="navigation budget for this run")
        sub.add_argument("--cookies-file", type=Path, help="private Netscape/Playwright B17 cookies; require verified login")
        sub.add_argument("--browser-profile", type=Path, help="dedicated persistent Playwright profile; require verified login")
        if name not in ("inspect", "login", "filters"):
            sub.add_argument("--output", type=Path, required=True, help="JSONL output (checkpoint beside it)")
            sub.add_argument("--max-profiles", type=positive, default=50, help="total successful records, including resumed ones")
            sub.add_argument("--resume", action="store_true")
        if name == "crawl":
            sub.add_argument("--max-pages", type=positive, default=10000, help="maximum new catalog pages per run")
        if name == "filters":
            sub.add_argument("--html", type=Path, help="read a saved HTML page without network access")
            sub.add_argument("--city-html", type=Path, help="optional saved city picker HTML for discovered route labels")
            sub.add_argument("--output", type=Path, help="write the complete reference as UTF-8 JSON")
            sub.add_argument("--markdown", type=Path, help="write a complete readable filter guide")
        if name == "profiles":
            sub.add_argument("--urls-file", type=Path, help="one profile URL per line, # comments allowed")
    sub = subs.add_parser("export")
    sub.add_argument("--input", type=Path, required=True)
    sub.add_argument("--output", type=Path, required=True)
    sub.add_argument("--format", choices=("json", "csv"), required=True)
    sub = subs.add_parser("build-url", help="build and validate a URL offline against an exported filter reference")
    sub.add_argument("--catalog", type=Path, required=True, help="JSON reference produced by filters")
    sub.add_argument("--set", dest="selections", action="append", default=[], metavar="PARAM=VALUE", help="repeat for multiple fields; numeric multi-values may be comma-separated")
    sub.add_argument("--base-url", help="same catalog context; source URL is used by default")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "build-url":
            from .urlbuilder import build_url, parse_assignments
            reference = json.loads(args.catalog.read_text(encoding="utf-8"))
            print(build_url(reference, parse_assignments(args.selections), args.base_url))
            return 0
        if args.command == "filters" and args.html:
            return export_filter_reference(args, read_saved_html(args.html), fetched_live=False)
        if args.command == "export":
            if args.input.resolve() == args.output.resolve():
                raise ValueError("Export destination must differ from input")
            export_records(read_jsonl(args.input), args.output, args.format)
            return 0
        if not all(math.isfinite(n) for n in (args.delay, args.timeout, args.jitter)) or args.delay < 1 or args.timeout <= 0 or args.jitter < 0:
            raise ValueError("--delay must be >=1 and --timeout must be positive")
        if args.cookies_file and args.browser_profile:
            raise ValueError("Choose either --cookies-file or --browser-profile")
        gate = AccessGate(args.access_state, delay=args.delay, jitter=args.jitter)
        if args.command == "login":
            if not args.browser_profile:
                raise ValueError("login requires a dedicated --browser-profile directory")
            from .browser import BrowserClient
            with gate.slot():
                with BrowserClient(args.browser_profile, delay=args.delay, timeout=args.timeout) as browser:
                    try:
                        browser.login()
                    except AccessError as exc:
                        if 'login is absent or expired' not in str(exc):
                            gate.block(3600)
                        raise
            print("B17 session verified and saved in the dedicated browser profile")
            return 0
        if args.browser_profile:
            from .browser import BrowserClient
            transport = BrowserClient(args.browser_profile, delay=args.delay, timeout=args.timeout)
        else:
            transport = HttpClient(args.delay, args.timeout, cookies_file=args.cookies_file)
        client = ManagedClient(transport, gate, args.max_requests)
        if args.command == "filters":
            return export_filter_reference(args, client.get(normalize_url(args.url)), fetched_live=True)
        if args.command == "inspect":
            url = normalize_url(args.url)
            catalog = parse_catalog(client.get(url), url)
            print(json.dumps(catalog, ensure_ascii=False, indent=2))
            return 0
        if args.command == "crawl":
            url = normalize_url(args.url)
            if not urlsplit(url).path.startswith(("/psiholog/", "/online/")):
                raise ValueError("Use a city catalog /psiholog/CITY/ or /online/ URL")
            start_page = int(parse_qs(urlsplit(url).query).get("page", ["1"])[0])
            if start_page < 1:
                raise ValueError("page must be >=1")
            source = {"mode": "crawl", "url": url, "start_page": start_page}
        else:
            urls = args.url or []
            if args.urls_file:
                urls.extend(line.strip() for line in args.urls_file.read_text(encoding="utf-8").splitlines()
                            if line.strip() and not line.lstrip().startswith("#"))
            urls = list(dict.fromkeys(normalize_url(url, profile=True) for url in urls))
            if not urls:
                raise ValueError("Provide --url or --urls-file")
            source = {"mode": "profiles", "urls": urls}
        source["access_mode"] = "browser_account" if args.browser_profile else "cookie_account" if args.cookies_file else "anonymous"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        output_lock = Path(str(args.output) + ".lock").open("a")
        try:
            fcntl.flock(output_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another collector is already writing this output") from exc
        collector = Collector(client, args.output, source, resume=args.resume)
        report = collector.run(args.max_profiles, getattr(args, "max_pages", 10000))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if report["fatal_error"]:
            print(report["fatal_error"], file=sys.stderr)
        return 2 if report["status"] in ("stopped_error", "partial_errors", "interrupted", "pagination_unverified") or report["failures_this_run"] else 0
    except (ValueError, OSError, FetchError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    finally:
        if 'output_lock' in locals():
            output_lock.close()
        if 'client' in locals():
            client.close()


def read_saved_html(path: Path) -> str:
    """Read UTF-8 captures or B17's legacy Windows-1251 HTML without executing it."""
    data = path.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("windows-1251")


def export_filter_reference(args, html: str, fetched_live: bool) -> int:
    """Export controls and provenance from one fetched or explicitly saved page."""
    from .filters import extract_filter_catalog, render_filter_guide
    from .http import validate_page
    validate_page(html, args.url)
    provenance = {"mode": "live_http_or_browser" if fetched_live else "saved_html",
                  "exported_at": datetime.now(timezone.utc).isoformat(),
                  "html_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest()}
    if not fetched_live:
        provenance["captured_at"] = datetime.fromtimestamp(args.html.stat().st_mtime, timezone.utc).isoformat()
        provenance["capture_time_basis"] = "local capture file modification time"
    cities = read_saved_html(args.city_html) if args.city_html else None
    if args.city_html:
        provenance["city_index_capture"] = {
            "captured_at": datetime.fromtimestamp(args.city_html.stat().st_mtime, timezone.utc).isoformat(),
            "capture_time_basis": "local capture file modification time",
            "html_sha256": hashlib.sha256(cities.encode("utf-8")).hexdigest(),
            "coverage": "city links in this saved index only; not every B17 city guaranteed",
        }
    reference = extract_filter_catalog(html, normalize_url(args.url), provenance=provenance, city_html=cities)
    inputs = {path.resolve() for path in (args.html, args.city_html) if path is not None}
    if args.output and args.output.resolve() in inputs:
        raise ValueError("Reference output must differ from the input HTML")
    if args.markdown and args.markdown.resolve() in inputs:
        raise ValueError("Markdown output must differ from the input HTML")
    if args.markdown and args.output and args.markdown.resolve() == args.output.resolve():
        raise ValueError("Markdown and JSON outputs must differ")
    if args.output:
        atomic_json(args.output, reference)
    else:
        print(json.dumps(reference, ensure_ascii=False, indent=2))
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render_filter_guide(reference), encoding="utf-8")
    return 0
