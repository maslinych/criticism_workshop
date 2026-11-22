"""A minimal client for the LiteLLM service (OpenAI-compatible chat API).

The service address and key come from environment variables whose names are
set in config.yaml (`llm`); they are never written into code or files.

Network problems and "busy" answers from the service (rate limit, server
errors) are retried here after a pause. They are not failures of the model's
answer, and they do not count as attempts. Other errors (a wrong key, an
unknown model) stop the run, so that no money is spent on requests that cannot
succeed.
"""

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

TRANSIENT_HTTP = {408, 409, 429, 500, 502, 503, 504}


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
                 transport_retries: int = 5, pause: float = 10.0, log=print):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key
        self.timeout = timeout
        self.transport_retries = transport_retries
        self.pause = pause
        self.log = log

    @classmethod
    def from_config(cls, cfg: dict, log=print) -> "LLMClient":
        llm = cfg["llm"]
        base, key = os.environ.get(llm["base_url_env"]), os.environ.get(llm["api_key_env"])
        if not base or not key:
            raise SystemExit(f"set the environment variables {llm['base_url_env']} (address of the "
                             f"LiteLLM service) and {llm['api_key_env']} (your key) before running")
        return cls(base, key, timeout=llm["timeout"], transport_retries=llm["transport_retries"],
                   pause=llm["pause"], log=log)

    def chat(self, model: str, messages: list[dict], settings: dict) -> Reply:
        body = {"model": model, "messages": messages}
        body.update({k: v for k, v in settings.items() if v is not None})
        data = json.dumps(body).encode("utf-8")
        for attempt in range(self.transport_retries + 1):
            request = urllib.request.Request(self.url, data=data, method="POST", headers={
                "Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:500]
                if e.code not in TRANSIENT_HTTP:
                    raise LLMError(f"the service refused the request (HTTP {e.code}): {detail}") from e
                problem = f"HTTP {e.code}"
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                problem = f"network problem: {e}"
            if attempt == self.transport_retries:
                raise LLMError(f"giving up after {attempt + 1} tries ({problem})")
            wait = self.pause * 2 ** attempt
            self.log(f"service busy or unreachable ({problem}); waiting {wait:.0f} s")
            time.sleep(wait)
        choice = payload["choices"][0]
        return Reply(text=choice["message"].get("content"), finish_reason=choice.get("finish_reason"),
                     usage=payload.get("usage") or {}, response_id=payload.get("id"),
                     model=payload.get("model"))
