"""Command line of the collector (B11), run from the root of the repository:

    .venv\\Scripts\\python -m collector check-sources   test each source
    .venv\\Scripts\\python -m collector run             a full run (phase 1 for now)
    .venv\\Scripts\\python -m collector run --phase 1   without AI
    .venv\\Scripts\\python -m collector run --dry-run   write nothing, show what would be written
    .venv\\Scripts\\python -m collector validate        check the existing cards.json

The console shows counts only. The names held back and the details of refused cards go to the
local journal, collector/logs/collector.log, which Git ignores.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from pydantic import ValidationError

from . import cards, config, output
from .models import Feed
from .sources import Fetcher, SourceError, certfr, kev, ransomware_live
from .store import Store
from .text import french_date

log = logging.getLogger("collector")
LEVEL_NAMES = {"critique": "Critique", "grave": "Grave", "significative": "Significative", "mineure": "Mineure"}
SOURCE_OF_CARD = {"kev": "CISA", "certfr": "CERT-FR", "rl": "ransomware.live"}


@dataclass
class Report:
    name: str
    state: str  # "ok", "échec" or "sautée"
    detail: str


def shown(path) -> str:
    return str(path.relative_to(config.ROOT))


def open_journal() -> logging.Handler:
    config.JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(config.JOURNAL_PATH, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return handler


def read_sources(fetcher: Fetcher, now: datetime, key: str | None):
    reports, entries, alerts, claims = [], [], [], []
    try:
        catalogue = kev.fetch(fetcher)
        entries = kev.recent(catalogue, now)
        reports.append(Report(kev.NAME, "ok", f"{len(catalogue)} entrées lues, {len(entries)} ajoutées ces 7 derniers jours"))
    except SourceError as error:
        reports.append(Report(kev.NAME, "échec", str(error)))
    try:
        feed = certfr.fetch(fetcher)
        alerts = certfr.with_page_cves(fetcher, certfr.recent(feed, now))
        reports.append(Report(certfr.NAME, "ok", f"{len(feed)} alertes lues, {len(alerts)} de moins de 7 jours"))
    except SourceError as error:
        reports.append(Report(certfr.NAME, "échec", str(error)))
    if key is None:
        reports.append(Report(ransomware_live.NAME, "sautée", f"clé absente ({config.RANSOMWARE_LIVE_KEY} vide dans .env)"))
    else:
        try:
            claims, read = ransomware_live.fetch(fetcher, now, key)
            countries = ", ".join(config.TRACKED_COUNTRIES)
            reports.append(Report(ransomware_live.NAME, "ok", f"{read} revendications lues, {len(claims)} visant {countries} ces 7 derniers jours"))
        except SourceError as error:
            reports.append(Report(ransomware_live.NAME, "échec", ransomware_live.explain(error)))
    for report in reports:
        log.info("source %s : %s, %s", report.name, report.state, report.detail)
    return reports, entries, alerts, claims


def print_summary(now, reports, data, rejected, held, outcome, *, dry_run: bool) -> None:
    attacks = data["attacks"] if data else []
    print(f"Collecte du {french_date(now.date())} à {now:%H} h {now:%M} UTC, phase 1 (sans IA)")
    print("Sources :")
    for report in reports:
        print(f"  {report.name} : {report.state}, {report.detail}")
    levels = Counter(card["severity"] for card in attacks)
    origins = Counter(SOURCE_OF_CARD.get(card["id"].split("-")[0], "?") for card in attacks)
    by_level = ", ".join(f"{name} {levels[level]}" for level, name in LEVEL_NAMES.items() if levels[level])
    by_source = ", ".join(f"{name} {count}" for name, count in origins.items())
    print(f"Cartes {'prêtes' if dry_run else 'retenues'} : {len(attacks)}" + (f" ({by_level} ; {by_source})" if attacks else ""))
    print(f"Cartes rejetées : {len(rejected)}")
    for card_id, why in rejected:
        print(f"  {card_id} : {why}")
    print(f"Mises de côté : {len(held)}")
    for why, count in Counter(why for why, _ in held).items():
        print(f"  {count} : {why}")
    if held or rejected:
        print(f"  Détails dans le journal local : {shown(config.JOURNAL_PATH)}")
    kept_french = [card for card in attacks if card.get("untranslated")]
    if kept_french:
        print(f"Titres gardés en français dans la version anglaise : {len(kept_french)}")
        for card in kept_french:
            print(f"  {card['id']} : {card['title']['fr']}")
    print("Appels à l'IA : 0 (la phase 2 n'est pas encore construite)")
    print(f"{shown(config.OUTPUT_PATH)} : {outcome}")
    if dry_run and attacks:
        print("Ce qui serait écrit :")
        for card in attacks:
            print(f"  {LEVEL_NAMES[card['severity']]:<13} {card['first_seen'][:10]}  {card['title']['fr']}")


def run(args: argparse.Namespace, *, transport: httpx.BaseTransport | None, now: datetime | None) -> int:
    if args.phase == 2:
        print("La phase 2 (articles de presse lus par l'IA) n'est pas encore construite.")
        return 2
    now = now or datetime.now(timezone.utc)
    key = ransomware_live.api_key()
    with Store(config.STATE_PATH) as store, Fetcher(store, transport=transport) as fetcher:
        reports, entries, alerts, claims = read_sources(fetcher, now, key)
    built, held = cards.build(entries, alerts, claims)
    valid, rejected = output.check(built)
    for why, detail in held:
        log.info("mise de côté : %s : %s", why, detail)
    for card_id, why in rejected:
        log.warning("rejetée : %s : %s", card_id, why)
    sources_ok = sum(report.state == "ok" for report in reports)
    outcome, data = output.publish(config.OUTPUT_PATH, valid, now, sources_ok=sources_ok, dry_run=args.dry_run)
    log.info("%s : %s", shown(config.OUTPUT_PATH), outcome)
    print_summary(now, reports, data, rejected, held, outcome, dry_run=args.dry_run)
    return 0 if sources_ok else 1


def check_sources(*, transport: httpx.BaseTransport | None, now: datetime | None) -> int:
    now = now or datetime.now(timezone.utc)
    key = ransomware_live.api_key()
    failures = 0
    with Fetcher(None, transport=transport) as fetcher:
        try:
            catalogue = kev.fetch(fetcher)
            print(f"{kev.NAME} : répond ({len(catalogue)} entrées, {len(kev.recent(catalogue, now))} ajoutées ces 7 derniers jours)")
        except SourceError as error:
            failures += 1
            print(f"{kev.NAME} : ne répond pas ({error})")
        try:
            feed = certfr.fetch(fetcher)
            print(f"{certfr.NAME} : répond ({len(feed)} alertes dans le flux, {len(certfr.recent(feed, now))} de moins de 7 jours)")
        except SourceError as error:
            failures += 1
            print(f"{certfr.NAME} : ne répond pas ({error})")
        if key is None:
            print(f"{ransomware_live.NAME} : non testée, clé absente ({config.RANSOMWARE_LIVE_KEY} vide dans .env)")
        else:
            try:
                claims, read = ransomware_live.fetch(fetcher, now, key)
                print(f"{ransomware_live.NAME} : répond ({read} revendications lues, {len(claims)} de moins de 7 jours dans les pays suivis)")
            except SourceError as error:
                failures += 1
                print(f"{ransomware_live.NAME} : ne répond pas ({ransomware_live.explain(error)})")
    return 1 if failures else 0


def validate() -> int:
    path = config.OUTPUT_PATH
    if not path.exists():
        print(f"{shown(path)} : absent. Lancer d'abord : .venv\\Scripts\\python -m collector run")
        return 1
    try:
        feed = Feed.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except ValidationError as error:
        print(f"{shown(path)} : invalide ({output.reason(error)})")
        return 1
    except ValueError:
        print(f"{shown(path)} : invalide (JSON illisible)")
        return 1
    levels = Counter(card.severity for card in feed.attacks)
    by_level = ", ".join(f"{name} {levels[level]}" for level, name in LEVEL_NAMES.items() if levels[level])
    print(f"{shown(path)} : valide, {len(feed.attacks)} cartes" + (f" ({by_level})" if by_level else "") + f", collecte du {feed.generated_at}")
    return 0


def main(
    argv: list[str] | None = None,
    *,
    transport: httpx.BaseTransport | None = None,
    now: datetime | None = None,
) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(
        prog="python -m collector",
        description="Collecteur de Tocsin : lit des sources fiables et écrit frontend/public/data/cards.json.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check-sources", help="teste chaque source")
    run_parser = commands.add_parser("run", help="un passage complet")
    run_parser.add_argument("--phase", type=int, choices=(1, 2), help="1 : sans IA")
    run_parser.add_argument("--dry-run", action="store_true", help="n'écrit rien, affiche ce qui serait écrit")
    run_parser.add_argument("--max-ai-calls", type=int, default=40, help="appels à l'IA au plus par passage (phase 2)")
    commands.add_parser("validate", help="valide le cards.json existant")
    args = parser.parse_args(argv)
    handler = open_journal()
    try:
        if args.command == "check-sources":
            return check_sources(transport=transport, now=now)
        if args.command == "run":
            return run(args, transport=transport, now=now)
        return validate()
    finally:
        log.removeHandler(handler)
        handler.close()


if __name__ == "__main__":
    sys.exit(main())
