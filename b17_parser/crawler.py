"""Checkpointed catalog discovery and profile collection."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .catalog import normalize_url, page_url, parse_catalog
from .http import AccessError, BudgetReached, FetchError
from .profile import parse_profile
from .storage import append_record, atomic_json, read_jsonl


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Collector:
    """Keep the output as the authority for completed records across crashes.

    Checkpoints retain all discovered cards before fetching any profile. A crash
    after an output append but before a checkpoint cannot produce a duplicate.
    A checkpoint belongs to one exact catalog or ordered list of profile URLs.
    """

    def __init__(self, client, output: Path, source: dict, resume: bool = False):
        self.client, self.output, self.source = client, Path(output), source
        self.state_path = Path(str(output) + ".state.json")
        self.report_path = Path(str(output) + ".report.json")
        self.errors_path = Path(str(output) + ".errors.jsonl")
        if not resume and (self.output.exists() or self.state_path.exists()):
            raise ValueError("Output/checkpoint already exists; use --resume or another output")
        if resume and not self.state_path.exists():
            raise ValueError("Resume requires the matching .state.json checkpoint")
        if resume:
            self.state = json.loads(self.state_path.read_text(encoding="utf-8"))
            if self.state.get("source") != source:
                raise ValueError("Checkpoint source differs; use the original URL/list or another output")
            if self.state.get("completed", 0) and not self.output.exists():
                raise ValueError("Checkpoint has completed profiles but the output is missing")
        else:
            self.state = {"version": 1, "source": source, "next_page": source.get("start_page", 1),
                          "cards": [], "pages": [], "catalog_exhausted": source["mode"] == "profiles",
                          "total_reported": None, "filter_verification": [], "completed": 0}
            if source["mode"] == "profiles":
                self.state["cards"] = [{"url": url} for url in source["urls"]]
        records = read_jsonl(self.output, repair_tail=resume)
        self.done = {r["url"] for r in records}
        self.id_urls = {r["id"]: r["url"] for r in records if r.get("id")}
        self.done_ids = set(self.id_urls)
        self.state.setdefault("resolved_urls", {})
        self.state.setdefault("warnings", [])
        if self.state.get("completed", 0) > len(self.done):
            raise ValueError("Output has fewer complete records than the checkpoint")
        self.state["completed"] = len(self.done)
        self.save()

    def save(self):
        self.state["updated_at"] = now()
        atomic_json(self.state_path, self.state)

    def is_done(self, card):
        return (card["url"] in self.done or self.state["resolved_urls"].get(card["url"]) in self.done
                or bool(card.get("id") and card["id"] in self.done_ids))

    def run(self, max_profiles: int, max_pages: int = 10000) -> dict:
        attempts, pages_this_run, failures, fatal = set(), 0, [], None
        # Site totals describe the whole catalog, not a suffix starting later.
        starts_at_first_page = self.source.get("start_page", 1) == 1
        status = "limit_reached"
        try:
            while len(self.done) < max_profiles:
                pending = [c for c in self.state["cards"]
                           if not self.is_done(c) and c["url"] not in attempts]
                if pending:
                    card = pending[0]
                    url = card["url"]
                    attempts.add(url)
                    try:
                        html = self.client.get(url)
                        final_url = normalize_url(getattr(self.client, "last_url", None) or url, profile=True)
                        record = parse_profile(html, final_url, card=card)
                        self.state["resolved_urls"][url] = self.id_urls.get(record.get("id"), final_url)
                        if record["url"] in self.done or (record.get("id") and record["id"] in self.done_ids):
                            self.save()
                            continue
                        record["catalog_source"] = self.source.get("url")
                        record["requested_url"] = url
                        append_record(self.output, record)
                        self.done.add(record["url"])
                        if record.get("id"):
                            self.done_ids.add(record["id"])
                            self.id_urls[record["id"]] = record["url"]
                        self.state["completed"] = len(self.done)
                        self.save()
                    except (AccessError, BudgetReached):
                        raise
                    except (FetchError, ValueError) as exc:
                        error = {"url": url, "error": str(exc), "at": now()}
                        append_record(self.errors_path, error)
                        failures.append(error)
                    continue
                if self.state["catalog_exhausted"]:
                    status = "partial_errors" if failures else "available_results_exhausted"
                    if self.state.get("terminal_evidence") == "no_pagination_marker":
                        status = "pagination_unverified"
                    if (self.source["mode"] == "crawl" and starts_at_first_page
                            and self.state["total_reported"] is not None
                            and len(self.state["cards"]) < self.state["total_reported"]):
                        status = "pagination_unverified"
                    break
                if pages_this_run >= max_pages:
                    status = "page_limit_reached"
                    break
                page = self.state["next_page"]
                url = page_url(self.source["url"], page)
                html = self.client.get(url)
                final_url = getattr(self.client, "last_url", None) or url
                catalog = parse_catalog(html, url)
                if normalize_url(final_url) != normalize_url(url):
                    # Filters must be verifiable at the actual redirected catalog too.
                    parse_catalog(html, final_url)
                urls = {c["url"] for c in self.state["cards"]}
                fresh = [c for c in catalog["cards"] if c["url"] not in urls]
                if catalog["cards"] and not fresh:
                    raise ValueError(f"Catalog repeated known profiles on page {page}; cannot prove exhaustion")
                if (not catalog["cards"] and starts_at_first_page
                        and self.state["total_reported"] is not None
                        and len(urls) < self.state["total_reported"]):
                    raise ValueError(f"Empty page {page} before reported result count; collection incomplete")
                if self.state["pages"] and catalog["city"] != self.state["pages"][0]["city"]:
                    raise ValueError("Catalog city changed during pagination")
                if catalog["total"] is not None:
                    self.state["total_reported"] = catalog["total"]
                self.state["cards"].extend(fresh)
                self.state["pages"].append({"page": page, "url": url, "city": catalog["city"],
                                            "cards": len(catalog["cards"]), "new": len(fresh),
                                            "selected_filters": catalog["selected_filters"],
                                            "terminal_evidence": catalog.get("terminal_evidence"),
                                            "pagination": catalog.get("pagination")})
                self.state["warnings"].extend(catalog.get("warnings", []))
                self.state["terminal_evidence"] = catalog.get("terminal_evidence")
                self.state["filter_verification"] = catalog["selected_filters"]
                self.state["next_page"] = catalog["next_page"]
                self.state["catalog_exhausted"] = catalog["next_page"] is None or not catalog["cards"]
                pages_this_run += 1
                self.save()
        except BudgetReached as exc:
            status, fatal = "request_limit_reached", None
        except KeyboardInterrupt:
            status, fatal = "interrupted", "Interrupted by user; resume with the same source/output"
        except (FetchError, ValueError) as exc:
            status, fatal = "stopped_error", str(exc)
        self.save()
        report = {"source": self.source, "status": status, "completed": len(self.done),
                  "discovered": len(self.state["cards"]), "pages_collected": len(self.state["pages"]),
                  "pages_this_run": pages_this_run, "total_reported_by_site": self.state["total_reported"],
                  "catalog_exhausted": self.state["catalog_exhausted"], "failures_this_run": failures,
                  "pending_profiles": len([c for c in self.state["cards"] if not self.is_done(c)]),
                  "fatal_error": fatal, "http_requests_this_run": getattr(self.client, "requests", None),
                  "finished_at": now(), "warnings": self.state["warnings"],
                  "terminal_evidence": self.state.get("terminal_evidence"),
                  "coverage_note": (
                      f"Only results available to this session starting at catalog page {self.source.get('start_page', 1)}; "
                      "not a guarantee of all B17 profiles."
                      if self.source["mode"] == "crawl" else
                      "Only results available to this session; not a guarantee of all B17 profiles.")}
        atomic_json(self.report_path, report)
        return report
