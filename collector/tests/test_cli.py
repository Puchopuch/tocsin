"""The command line (B11): the summary, the local journal, a run without key, a run when every
source fails, the dry run, validation, and no key anywhere (B12, with caplog)."""

import logging

from collector import config
from collector.__main__ import main

from .helpers import FAKE_KEY, SOURCES, collect, give_key, written


def test_run_writes_the_cards_and_prints_a_summary(isolated, capsys):
    give_key(isolated)
    assert collect("run") == 0
    printed = capsys.readouterr().out
    assert len(written()["attacks"]) == 11
    assert "Cartes retenues : 11" in printed
    assert "Cartes rejetées : 1" in printed
    assert "Mises de côté : 2" in printed
    assert "Appels à l'IA : 0" in printed
    assert "frontend\\public\\data\\cards.json : écrit" in printed or "frontend/public/data/cards.json : écrit" in printed


def test_names_held_back_stay_in_the_local_journal(isolated, capsys):
    give_key(isolated)
    collect("run")
    printed = capsys.readouterr().out
    journal = config.JOURNAL_PATH.read_text(encoding="utf-8")
    cards_file = config.OUTPUT_PATH.read_text(encoding="utf-8")
    for name in ("Dr Exemple Fictif", "Jean Fictif"):
        assert name not in printed
        assert name not in cards_file
        assert name in journal


def test_no_key_in_logs_console_journal_or_cards(isolated, capsys, caplog):
    caplog.set_level(logging.DEBUG)
    give_key(isolated)
    collect("run")
    collect("check-sources")
    refusing = {**SOURCES, config.RANSOMWARE_LIVE_API: (401, b'{"error": "invalid key"}')}
    collect("run", table=refusing)
    collect("check-sources", table=refusing)
    printed = capsys.readouterr()
    assert "clé refusée (HTTP 401)" in printed.out
    assert FAKE_KEY not in caplog.text
    assert FAKE_KEY not in printed.out + printed.err
    assert FAKE_KEY not in config.JOURNAL_PATH.read_text(encoding="utf-8")
    assert FAKE_KEY not in config.OUTPUT_PATH.read_text(encoding="utf-8")


def test_without_key_ransomware_live_is_skipped_and_the_rest_works(capsys):
    assert collect("run", "--phase", "1") == 0
    printed = capsys.readouterr().out
    assert "ransomware.live, revendications : sautée, clé absente" in printed
    assert len(written()["attacks"]) == 9


def test_when_every_source_fails_the_old_file_stays(capsys):
    collect("run")
    before = config.OUTPUT_PATH.read_bytes()
    broken = {prefix: (503, b"") for prefix in SOURCES}
    assert collect("run", table=broken) == 1
    assert config.OUTPUT_PATH.read_bytes() == before
    assert "gardé tel quel : toutes les sources ont échoué" in capsys.readouterr().out


def test_dry_run_writes_nothing(capsys):
    assert collect("run", "--dry-run") == 0
    assert not config.OUTPUT_PATH.exists()
    printed = capsys.readouterr().out
    assert "Ce qui serait écrit" in printed
    assert "Faille exploitée dans Synology DSM" in printed


def test_validate(capsys):
    assert main(["validate"]) == 1
    collect("run")
    assert main(["validate"]) == 0
    config.OUTPUT_PATH.write_text('{"generated_at": "2026-11-20", "attacks": []}', encoding="utf-8")
    assert main(["validate"]) == 1
    assert "invalide" in capsys.readouterr().out


def test_without_a_mistral_key_phase_two_is_skipped_and_the_rest_works(capsys):
    assert collect("run", "--phase", "2") == 0
    printed = capsys.readouterr().out
    assert "Presse, lue par l'IA (Mistral) : sautée, clé absente (MISTRAL_API_KEY vide dans .env)" in printed
    assert "Appels à l'IA : 0 (phase 2 sautée)" in printed
    assert len(written()["attacks"]) == 9
