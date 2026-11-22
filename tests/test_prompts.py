"""The prompt files: their worked examples must pass the real checks."""

import json
import re

import pytest

from ncse import checks
from ncse.config import load_config
from ncse.prompts import PROMPTS_DIR, load_prompt


def code_blocks(path):
    return re.findall(r"```\n(.*?)```", path.read_text(encoding="utf-8"), re.S)


def test_analyst_example_passes_the_checks():
    blocks = code_blocks(PROMPTS_DIR / "analyst" / "v1" / "system.md")
    text, raw = blocks[1], blocks[2]
    check = checks.check_analyst(raw, text, load_prompt("analyst", "v1").schema)
    assert check.ok, check.errors
    assert not check.flags
    assert checks.statement_count(check.result) == 4


def test_reviewer_example_matches_its_schema():
    raw = code_blocks(PROMPTS_DIR / "reviewer" / "v1" / "system.md")[-1]
    assert not checks.schema_errors(json.loads(raw), load_prompt("reviewer", "v1").schema)


@pytest.mark.parametrize("step", ["analyst", "reviewer"])
def test_configured_prompt_versions_exist_and_render(step):
    cfg = load_config()
    prompt = load_prompt(step, cfg["annotation"][step]["prompt_version"])
    values = {"periodical": "The Leader", "issue_date": "1852-01-17", "article_id": "X",
              "heading": "H", "text": "Some text {{not a placeholder}}", "statements_json": "{}"}
    system, user = prompt.render(**values)
    assert system["content"] == prompt.system
    assert "Some text {{not a placeholder}}" in user["content"]  # article text inserted unchanged
    assert "{{periodical}}" not in user["content"]
    with pytest.raises(ValueError):
        prompt.render(text="only text")
