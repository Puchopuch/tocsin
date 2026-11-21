"""Command line of the collector (B11), run from the root of the repository:

    .venv\\Scripts\\python -m collector check-sources   test each source
    .venv\\Scripts\\python -m collector run             a full run (phase 2 needs a Mistral key)
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

from . import ai, cards, cluster, config, output, press, severity
from .models import Feed
from .sources import Fetcher, SourceError, certfr, kev, ransomware_live, rss
from .store import Store
from .text import french_date

log = logging.getLogger("collector")
LEVEL_NAMES = {"critique": "Critique", "grave": "Grave", "significative": "Significative", "mineure": "Mineure"}
SOURCE_OF_CARD = {"kev": "CISA", "certfr": "CERT-FR", "rl": "ransomware.live", "press": "presse"}
PRESS = "Presse, lue par l'IA (Mistral)"


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
        alerts = certfr.with_page_details(fetcher, certfr.recent(feed, now))
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
            # A refused key is a setting to fix, not a source down: the other sources still update the site.
            state = "sautée" if error.status in (401, 403) else "échec"
            reports.append(Report(ransomware_live.NAME, state, ransomware_live.explain(error)))
    for report in reports:
        log.info("source %s : %s, %s", report.name, report.state, report.detail)
    return reports, entries, alerts, claims


def read_press(fetcher: Fetcher, store: Store, now: datetime, args, entries, built: list[dict]):
    """Phase 2, when a Mistral key is there: the press cards, and the CISA cards translated."""
    if args.phase == 1:
        return [Report(PRESS, "sautée", "phase 1 seule demandée (sans IA)")], None
    key = ai.api_key()
    if key is None:
        return [Report(PRESS, "sautée", f"clé absente ({config.MISTRAL_KEY} vide dans .env)")], None
    client = ai.Mistral(fetcher, key, store, max_calls=args.max_ai_calls)
    result = press.read(fetcher, client, now, {entry.cve: entry for entry in entries}, built)
    reports = [Report(site, state, detail) for site, state, detail in result.feeds]
    if result.stopped == ai.AiError.MESSAGES["cle_refusee"]:
        reports.append(Report(PRESS, "sautée", "clé Mistral refusée : vérifier MISTRAL_API_KEY dans .env"))
    elif result.stopped:
        reports.append(Report(PRESS, "échec", result.stopped))
    else:
        budget = ", budget d'appels atteint" if result.budget_reached else ""
        reports.append(Report(PRESS, "ok", f"{len(result.cards)} cartes de presse, {result.translated} textes de la CISA traduits{budget}"))
    for why, detail in result.rejected:
        log.warning("rejetée (IA) : %s : %s", why, detail)
    return reports, (result, client)


def print_summary(now, reports, data, rejected, held, outcome, *, dry_run: bool, phase2=None) -> None:
    attacks = data["attacks"] if data else []
    used = "phases 1 et 2 (avec l'IA)" if phase2 else "phase 1 (sans IA)"
    print(f"Collecte du {french_date(now.date())} à {now:%H} h {now:%M} UTC, {used}")
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
    if phase2:
        result, client = phase2
        print(f"Appels à l'IA : {client.calls} sur {client.max_calls} ({client.left} restants), "
              f"{client.cached} réponses déjà connues réutilisées ; modèle {client.model}")
        print(f"Articles de presse sur une attaque : {result.articles}, sans incident établi : {result.not_incidents}, "
              f"rejetés : {len(result.rejected)}")
        for why, count in Counter(detail.split(" ; ")[0] for _, detail in result.rejected).items():
            print(f"  {count} : {why}")
    else:
        print("Appels à l'IA : 0 (phase 2 sautée)")
    print(f"{shown(config.OUTPUT_PATH)} : {outcome}")
    if dry_run and attacks:
        print("Ce qui serait écrit :")
        for card in attacks:
            print(f"  {LEVEL_NAMES[card['severity']]:<13} {card['first_seen'][:10]}  {card['title']['fr']}")


def run(args: argparse.Namespace, *, transport: httpx.BaseTransport | None, now: datetime | None) -> int:
    now = now or datetime.now(timezone.utc)
    key = ransomware_live.api_key()
    with Store(config.STATE_PATH) as store, Fetcher(store, transport=transport) as fetcher:
        reports, entries, alerts, claims = read_sources(fetcher, now, key)
        built, held = cards.build(entries, alerts, claims)
        press_reports, phase2 = read_press(fetcher, store, now, args, entries, built)
    reports += press_reports
    if phase2:
        built += phase2[0].cards
        held += phase2[0].held
    merged = [severity.cap_claim(card) for card in cluster.merge(built)]
    valid, rejected = output.check(merged)
    for why, detail in held:
        log.info("mise de côté : %s : %s", why, detail)
    for card_id, why in rejected:
        log.warning("rejetée : %s : %s", card_id, why)
    sources_ok = sum(report.state == "ok" for report in reports)
    sources_failed = sum(report.state == "échec" for report in reports)
    try:
        outcome, data = output.publish(
            config.OUTPUT_PATH, valid, now, sources_ok=sources_ok, sources_failed=sources_failed, dry_run=args.dry_run
        )
    except OSError as error:  # disk full, file locked...: the previous file stays whole
        outcome, data, sources_failed = f"gardé tel quel : écriture impossible ({type(error).__name__})", None, 1
    log.info("%s : %s", shown(config.OUTPUT_PATH), outcome)
    print_summary(now, reports, data, rejected, held, outcome, dry_run=args.dry_run, phase2=phase2)
    return 0 if sources_ok and not sources_failed else 1


def key_status(fetcher: Fetcher, key, url: str, params: dict | None = None) -> tuple[str, bytes | None]:
    """« absente », « valide » or « refusée », after one request to the API of the key; never the
    key itself."""
    if key is None:
        return "absente", None
    try:
        return "valide", fetcher.get(url, params=params, key=key)
    except SourceError as error:
        if error.status in (401, 403):
            return "refusée", None
        return f"non vérifiée, l'API ne répond pas ({error})", None


def check_keys(fetcher: Fetcher, now: datetime) -> int:
    """The state of each key, and whether the model of config.py is still offered by Mistral."""
    print("Clés (jamais affichées) :")
    problems = 0
    ransomware_key = ransomware_live.api_key()
    state, _ = key_status(fetcher, ransomware_key, f"{config.RANSOMWARE_LIVE_API}/victims/",
                          {"country": config.TRACKED_COUNTRIES[0], "year": str(now.year), "month": f"{now.month:02d}"})
    print(f"  {config.RANSOMWARE_LIVE_KEY} : {state}")
    problems += state not in ("absente", "valide")
    state, body = key_status(fetcher, ai.api_key(), f"{config.MISTRAL_API}/models")
    print(f"  {config.MISTRAL_KEY} : {state}")
    problems += state not in ("absente", "valide")
    if body is not None:
        try:
            offered = {model.get("id") for model in json.loads(body).get("data", []) if isinstance(model, dict)}
        except (ValueError, AttributeError):
            offered = set()
        if config.MISTRAL_MODEL in offered:
            print(f"    modèle {config.MISTRAL_MODEL} : proposé par Mistral")
        else:
            problems += 1
            print(f"    modèle {config.MISTRAL_MODEL} : absent de la liste de Mistral, à changer dans collector/config.py (MISTRAL_MODEL)")
    return problems


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
        for site, url, lang in config.PRESS_FEEDS:
            try:
                articles = rss.parse(fetcher.get(url), site, lang)
                print(f"{site} : répond ({len(articles)} articles dans le flux ; lu seulement avec une clé Mistral)")
            except SourceError as error:
                failures += 1
                print(f"{site} : ne répond pas ({error})")
        failures += check_keys(fetcher, now)
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
    run_parser.add_argument("--phase", type=int, choices=(1, 2), help="1 : sans IA ; 2 (par défaut) : avec l'IA si une clé Mistral est là")
    run_parser.add_argument("--dry-run", action="store_true", help="n'écrit rien, affiche ce qui serait écrit")
    run_parser.add_argument("--max-ai-calls", type=int, default=config.MAX_AI_CALLS, help="appels à l'IA au plus par passage (phase 2)")
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
