"""Phase 2 from the command line, with a simulated AI: a full run, a second run without any new
call, keys missing, wrong or refused, and check-sources telling the state of each key without ever
showing it. No test reaches the real Mistral or ransomware.live."""

import json
import logging

import httpx

from collector import config

from .helpers import FAKE_KEY, MISTRAL, PRESS, SOURCES, collect, give_keys, honest, network, reply, written

MODELS = "https://api.mistral.ai/v1/models"


def mistral_calls(seen: list) -> int:
    return sum(str(request.url).startswith(MISTRAL) for request in seen)


def test_a_run_with_a_mistral_key_adds_press_cards_written_by_the_ai(isolated, capsys):
    give_keys(isolated, mistral=True, ransomware=True)
    seen = []
    assert collect(transport=network(seen=seen)) == 0
    printed = capsys.readouterr().out
    assert "phases 1 et 2 (avec l'IA)" in printed
    assert f"Appels à l'IA : {mistral_calls(seen)} sur 40" in printed and f"modèle {config.MISTRAL_MODEL}" in printed
    attacks = written()["attacks"]
    press = [card for card in attacks if card["id"].startswith("press-")]
    assert len(press) == 2 and all(card["ai"]["role"] == "redaction" for card in press)
    fictiville = next(card for card in press if "Fictiville" in card["victim"]["label"]["fr"])
    assert "ransomware.live" in [source["name"] for source in fictiville["sources"]]  # the claim joined the press card
    assert not any(card["id"].startswith("rl-") and "Fictiville" in card["victim"]["label"]["fr"] for card in attacks)
    translated = [card for card in attacks if card["id"].startswith("kev-") and card["ai"]]
    assert translated and all(card["ai"]["role"] == "traduction" and len(card["summary"]) == 2 for card in translated)
    assert FAKE_KEY not in printed and FAKE_KEY not in config.OUTPUT_PATH.read_text(encoding="utf-8")


def test_a_second_run_makes_no_new_call(isolated, capsys):
    give_keys(isolated)
    first, second = [], []
    collect(transport=network(seen=first))
    collect(transport=network(seen=second))
    assert mistral_calls(first) > 0 and mistral_calls(second) == 0
    assert "Appels à l'IA : 0 sur 40" in capsys.readouterr().out.split("Collecte du")[-1]


def test_a_refused_mistral_key_gives_a_clear_message_and_the_rest_works(isolated, capsys):
    give_keys(isolated)
    assert collect(transport=network(answers=lambda task, payload: reply(401))) == 0
    printed = capsys.readouterr().out
    assert "Presse, lue par l'IA (Mistral) : sautée, clé Mistral refusée : vérifier MISTRAL_API_KEY dans .env" in printed
    assert {card["id"].split("-")[0] for card in written()["attacks"]} == {"kev", "certfr"}
    assert "Traceback" not in printed


def test_a_refused_ransomware_live_key_is_skipped_not_a_failure(isolated, capsys):
    give_keys(isolated, mistral=False, ransomware=True)
    table = {**SOURCES, config.RANSOMWARE_LIVE_API: (403, b"")}
    assert collect(table=table) == 0
    assert "ransomware.live, revendications : sautée, clé refusée (HTTP 403)" in capsys.readouterr().out
    assert written()["attacks"]


def test_mistral_out_of_order_keeps_the_previous_cards(isolated, capsys):
    give_keys(isolated)
    assert collect(transport=network()) == 0
    before = config.OUTPUT_PATH.read_bytes()
    config.STATE_PATH.unlink()  # without its answers kept, the run has to call Mistral again
    assert collect(transport=network(answers=lambda task, payload: reply(503))) == 1
    assert config.OUTPUT_PATH.read_bytes() == before
    assert "Presse, lue par l'IA (Mistral) : échec, Mistral injoignable ou en erreur" in capsys.readouterr().out


def models(*names: str) -> bytes:
    return json.dumps({"object": "list", "data": [{"id": name, "object": "model"} for name in names]}).encode()


def test_check_sources_says_absent_for_each_missing_key(capsys, caplog):
    caplog.set_level(logging.DEBUG)
    collect("check-sources", table={**SOURCES, **PRESS})
    printed = capsys.readouterr().out
    assert f"  {config.RANSOMWARE_LIVE_KEY} : absente" in printed and f"  {config.MISTRAL_KEY} : absente" in printed
    assert "ZATAZ : répond (5 articles dans le flux ; lu seulement avec une clé Mistral)" not in printed  # the evil link is refused
    assert "ZATAZ : répond (4 articles dans le flux ; lu seulement avec une clé Mistral)" in printed


def test_check_sources_says_valid_or_refused_and_whether_the_model_is_offered(isolated, capsys, caplog):
    caplog.set_level(logging.DEBUG)
    give_keys(isolated, mistral=True, ransomware=True)
    valid = {**SOURCES, **PRESS, MODELS: (200, models("mistral-large-2512", config.MISTRAL_MODEL))}
    assert collect("check-sources", table=valid) == 0
    printed = capsys.readouterr().out
    assert f"  {config.RANSOMWARE_LIVE_KEY} : valide" in printed and f"  {config.MISTRAL_KEY} : valide" in printed
    assert f"modèle {config.MISTRAL_MODEL} : proposé par Mistral" in printed

    retired = {**valid, MODELS: (200, models("mistral-small-2999"))}
    assert collect("check-sources", table=retired) == 1
    assert "absent de la liste de Mistral, à changer dans collector/config.py (MISTRAL_MODEL)" in capsys.readouterr().out

    refused = {**SOURCES, **PRESS, MODELS: (401, b"{}"), config.RANSOMWARE_LIVE_API: (403, b"")}
    assert collect("check-sources", table=refused) == 1
    printed = capsys.readouterr().out
    assert f"  {config.RANSOMWARE_LIVE_KEY} : refusée" in printed and f"  {config.MISTRAL_KEY} : refusée" in printed
    assert FAKE_KEY not in printed and FAKE_KEY not in caplog.text


def test_the_mistral_key_goes_to_api_mistral_ai_only(isolated):
    give_keys(isolated)
    seen = []
    collect(transport=network(seen=seen))
    for request in seen:
        sent = request.headers.get("authorization")
        if str(request.url).startswith("https://api.mistral.ai/"):
            assert sent == f"Bearer {FAKE_KEY}"
        else:
            assert sent is None and FAKE_KEY not in str(request.url)
