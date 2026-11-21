"""Calls to the AI, Mistral (phase 2, B7). The AI reads; the code judges.

- Each user brings their own key (MISTRAL_API_KEY in .env), held as a SecretStr and sent to
  api.mistral.ai only. Without it, phase 2 is skipped with a clear message.
- Only the instructions (collector/prompts/) and the text to read are sent: no address, no name of
  site, no other data.
- A dated model (config.MISTRAL_MODEL), temperature 0.1, and an answer that must follow a strict
  JSON schema: any other field, or a missing one, makes the answer refused.
- At most --max-ai-calls requests per run (40); after HTTP 429, a growing wait, then phase 2 stops
  cleanly. An answer is kept in state.db by fingerprint of what was sent: the same text never
  costs a second call.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, SecretStr

from . import config
from .facts import strict_schema
from .sources import ApiKey, Fetcher, SourceError
from .store import Store

PROMPTS = Path(__file__).parent / "prompts"


def prompt(name: str) -> str:
    return (PROMPTS / f"{name}.txt").read_text(encoding="utf-8").strip()


def prompts_version() -> str:
    """A short fingerprint of every prompt: each card keeps the version that wrote it."""
    digest = hashlib.sha256()
    for path in sorted(PROMPTS.glob("*.txt")):
        digest.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()[:10]


def api_key() -> ApiKey | None:
    """The Mistral key, from the environment or .env; None when empty. Never shown."""
    value = os.environ.get(config.MISTRAL_KEY)
    if not value and config.ENV_PATH.exists():
        value = dotenv_values(config.ENV_PATH).get(config.MISTRAL_KEY)
    value = (value or "").strip()
    if not value:
        return None
    return ApiKey(header="Authorization", host="api.mistral.ai", secret=SecretStr(value), prefix="Bearer ")


class AiError(Exception):
    """Why the AI could not answer: "cle_refusee", "limite" (HTTP 429 again and again), "budget",
    "erreur" (network or server), "reponse_invalide" (outside the schema)."""

    MESSAGES = {
        "cle_refusee": "clé Mistral refusée",
        "limite": "trop de requêtes (HTTP 429), arrêt propre",
        "budget": "budget d'appels atteint",
        "erreur": "Mistral injoignable ou en erreur",
        "reponse_invalide": "réponse hors du schéma, refusée",
    }

    def __init__(self, reason: str) -> None:
        super().__init__(self.MESSAGES[reason])
        self.reason = reason


class Mistral:
    def __init__(
        self,
        fetcher: Fetcher,
        key: ApiKey,
        store: Store | None,
        *,
        max_calls: int = config.MAX_AI_CALLS,
        model: str = config.MISTRAL_MODEL,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.fetcher, self.key, self.store = fetcher, key, store
        self.max_calls, self.model, self.sleep = max_calls, model, sleep
        self.calls = 0  # requests sent in this run
        self.cached = 0  # answers read again from state.db

    @property
    def left(self) -> int:
        return max(0, self.max_calls - self.calls)

    def ask(self, task: str, instructions: str, text: str, answer: type[BaseModel]) -> BaseModel:
        """The answer of the AI to these instructions about this text, checked against the model."""
        schema = strict_schema(answer)
        fingerprint = hashlib.sha256(
            json.dumps([self.model, prompts_version(), task, instructions, text, schema], ensure_ascii=False).encode()
        ).hexdigest()
        if self.store is not None and (kept := self.store.answer(fingerprint)) is not None:
            try:
                parsed = answer.model_validate_json(kept)
                self.cached += 1
                return parsed
            except ValueError:
                pass
        payload = {
            "model": self.model,
            "temperature": config.AI_TEMPERATURE,
            "messages": [{"role": "system", "content": instructions}, {"role": "user", "content": text}],
            "response_format": {"type": "json_schema", "json_schema": {"name": task, "schema": schema, "strict": True}},
        }
        for attempt in range(3):
            if self.calls >= self.max_calls:
                raise AiError("budget")
            self.calls += 1
            try:
                body = self.fetcher.post_json(f"{config.MISTRAL_API}/chat/completions", payload, key=self.key)
            except SourceError as error:
                if error.status == 429:
                    self.sleep(2.0 * 2**attempt)
                    continue
                raise AiError("cle_refusee" if error.status in (401, 403) else "erreur") from None
            try:
                content = json.loads(body)["choices"][0]["message"]["content"]
                parsed = answer.model_validate_json(content)
            except (ValueError, KeyError, IndexError, TypeError):
                raise AiError("reponse_invalide") from None
            if self.store is not None:
                self.store.keep_answer(fingerprint, content)
            return parsed
        raise AiError("limite")
