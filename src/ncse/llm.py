"""A minimal client for the LiteLLM service (OpenAI-compatible chat API).

The service address and key come from environment variables whose names are
set in config.yaml (`llm`); they are never written into code or files.

Network problems and "busy" answers from the service (rate limit, server
errors) are retried here after a pause. They are not failures of the model's
answer, and they do not count as attempts. Other errors (a wrong key, an
unknown model) stop the run, so that no money is spent on requests that cannot
succeed.

A gateway error (HTTP 502, 504) or a time-out that comes only after a long wait
(`llm.slow_failure` seconds) is not retried either: the request ran into a time
limit, usually because the model thinks for too long, and asking again would
fail the same way after the same wait.

Waiting before a retry stops at once when the run is interrupted (`stop`).
"""

import json
import os
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

TRANSIENT_HTTP = {408, 409, 429, 500, 502, 503, 504}
GATEWAY_HTTP = {502, 504}


class LLMError(Exception):
    """An error that should stop the run (after finished work is saved)."""


@dataclass
class Reply:
    text: str | None
    finish_reason: str | None
    usage: dict
    response_id: str | None
    model: str | None


class LLMClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 600,
                 transport_retries: int = 5, pause: float = 10.0, slow_failure: float = 120.0,
                 log=print, clock=time.monotonic):
        self.base_url = base_url.rstrip("/")
        self.url = self.base_url + "/chat/completions"
        self.api_key = api_key
        self.timeout = timeout
        self.transport_retries = transport_retries
        self.pause = pause
        self.slow_failure = slow_failure
        self.log = log
        self.clock = clock
        self.stop = threading.Event()  # set by the runner when the run is interrupted

    @classmethod
    def from_config(cls, cfg: dict, log=print) -> "LLMClient":
        llm = cfg["llm"]
        base, key = os.environ.get(llm["base_url_env"]), os.environ.get(llm["api_key_env"])
        if not base or not key:
            raise SystemExit(f"set the environment variables {llm['base_url_env']} (address of the "
                             f"LiteLLM service) and {llm['api_key_env']} (your key) before running")
        return cls(base, key, timeout=llm["timeout"], transport_retries=llm["transport_retries"],
                   pause=llm["pause"], slow_failure=llm.get("slow_failure", 120), log=log)

    def chat(self, model: str, messages: list[dict], settings: dict) -> Reply:
        body = {"model": model, "messages": messages}
        body.update({k: v for k, v in settings.items() if v is not None})
        data = json.dumps(body).encode("utf-8")
        for attempt in range(self.transport_retries + 1):
            request = urllib.request.Request(self.url, data=data, method="POST", headers={
                "Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
            if self.stop.is_set():
                raise LLMError("the run was interrupted")
            sent_at = self.clock()
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:500]
                if e.code not in TRANSIENT_HTTP:
                    hint = ""
                    if e.code in (400, 404) and "model" in detail.lower():
                        hint = (" — check the model name in config.yaml; `uv run ncse models` lists the "
                                "names the service knows")
                    elif e.code in (401, 403) and "model" in detail.lower():
                        hint = (" — your key may not be allowed to use this model, even if `uv run ncse "
                                "models` lists it; choose another one in config.yaml")
                    raise LLMError(f"the service refused the request (HTTP {e.code}): {detail}{hint}") from e
                problem = f"HTTP {e.code}"
                slow = e.code in GATEWAY_HTTP
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                problem = f"network problem: {e}"
                slow = isinstance(e, TimeoutError) or isinstance(getattr(e, "reason", None), TimeoutError)
            waited = self.clock() - sent_at
            if slow and waited >= self.slow_failure:
                raise LLMError(f"the service gave up after waiting {waited:.0f} s ({problem}). The model "
                               "probably needs longer than the service allows for one answer, so asking "
                               "again would fail the same way. Choose a faster model, or one that does not "
                               "reason at length, in config.yaml")
            if attempt == self.transport_retries:
                raise LLMError(f"giving up after {attempt + 1} tries ({problem})")
            wait = self.pause * 2 ** attempt
            self.log(f"service busy or unreachable ({problem}); waiting {wait:.0f} s")
            if self.stop.wait(wait):
                raise LLMError("the run was interrupted")
        choice = payload["choices"][0]
        return Reply(text=choice["message"].get("content"), finish_reason=choice.get("finish_reason"),
                     usage=payload.get("usage") or {}, response_id=payload.get("id"),
                     model=payload.get("model"))

    def models(self) -> list[str]:
        """The model names the service offers (GET /models)."""
        request = urllib.request.Request(self.base_url + "/models",
                                         headers={"Authorization": f"Bearer {self.api_key}"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise LLMError(f"the service refused the request (HTTP {e.code}): "
                           f"{e.read().decode('utf-8', 'replace')[:500]}") from e
        return sorted(m["id"] for m in payload.get("data", []))
