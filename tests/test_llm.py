"""The LiteLLM client: retries when the service is busy, stops on other errors."""

import io
import json
import urllib.error

import pytest

from ncse import llm

OK = {"id": "r1", "model": "m", "usage": {"prompt_tokens": 5, "completion_tokens": 2},
      "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def scripted(monkeypatch, outcomes):
    sent = []

    def urlopen(request, timeout):
        sent.append(json.loads(request.data))
        item = outcomes.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(json.dumps(item).encode())

    monkeypatch.setattr(llm.urllib.request, "urlopen", urlopen)
    return sent


def http_error(code):
    return urllib.error.HTTPError("u", code, "x", {}, io.BytesIO(b"detail"))


def client(**kw):
    return llm.LLMClient("http://example.invalid/v1/", "key", pause=0, log=lambda m: None, **kw)


def test_busy_service_is_retried(monkeypatch):
    sent = scripted(monkeypatch, [http_error(429), urllib.error.URLError("down"), OK])
    reply = client().chat("m", [{"role": "user", "content": "hi"}], {"temperature": 0, "max_tokens": None})
    assert reply.text == "{}" and reply.usage["prompt_tokens"] == 5
    assert len(sent) == 3
    assert sent[0] == {"model": "m", "messages": [{"role": "user", "content": "hi"}], "temperature": 0}


def test_other_http_errors_stop_at_once(monkeypatch):
    sent = scripted(monkeypatch, [http_error(401)])
    with pytest.raises(llm.LLMError, match="HTTP 401"):
        client().chat("m", [], {})
    assert len(sent) == 1


def test_gives_up_after_the_configured_tries(monkeypatch):
    scripted(monkeypatch, [http_error(503)] * 3)
    with pytest.raises(llm.LLMError, match="giving up after 3 tries"):
        client(transport_retries=2).chat("m", [], {})


def test_credentials_come_from_the_environment(monkeypatch):
    cfg = {"llm": {"base_url_env": "T_URL", "api_key_env": "T_KEY", "timeout": 1,
                   "transport_retries": 0, "pause": 0}}
    monkeypatch.delenv("T_URL", raising=False)
    with pytest.raises(SystemExit, match="T_URL"):
        llm.LLMClient.from_config(cfg)
    monkeypatch.setenv("T_URL", "http://x/v1")
    monkeypatch.setenv("T_KEY", "k")
    assert llm.LLMClient.from_config(cfg).url == "http://x/v1/chat/completions"


def test_unknown_model_gets_a_hint(monkeypatch):
    err = urllib.error.HTTPError("u", 404, "x", {}, io.BytesIO(b"Unknown model/service"))
    scripted(monkeypatch, [err])
    with pytest.raises(llm.LLMError, match="ncse models"):
        client().chat("m", [], {})


def test_models_lists_names(monkeypatch):
    scripted_get = {"data": [{"id": "b"}, {"id": "a"}]}
    monkeypatch.setattr(llm.urllib.request, "urlopen",
                        lambda request, timeout: FakeResponse(json.dumps(scripted_get).encode()))
    assert client().models() == ["a", "b"]
