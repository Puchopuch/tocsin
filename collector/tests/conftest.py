"""Shared setup: no network at all, and each test in its own folder, so that no test ever reads or
writes the real cards.json, state.db, journal or .env."""

import socket

import pytest

from collector import config


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """B12: the tests never reach the network."""

    def refuse(*args, **kwargs):
        raise RuntimeError("network access is forbidden in tests")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "OUTPUT_PATH", tmp_path / "frontend" / "public" / "data" / "cards.json")
    monkeypatch.setattr(config, "STATE_PATH", tmp_path / "collector" / "state.db")
    monkeypatch.setattr(config, "JOURNAL_PATH", tmp_path / "collector" / "logs" / "collector.log")
    monkeypatch.setattr(config, "ENV_PATH", tmp_path / ".env")
    monkeypatch.delenv(config.RANSOMWARE_LIVE_KEY, raising=False)
    return tmp_path
