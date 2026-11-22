"""Loading the versioned prompt files (prompts/<step>/<version>/; D-022)."""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .config import PROJECT_ROOT

PROMPTS_DIR = PROJECT_ROOT / "prompts"
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


@dataclass
class Prompt:
    step: str
    version: str
    system: str
    user_template: str
    schema: dict
    sha256: str  # checksum of the three files, recorded with every request

    def render(self, **values: str) -> list[dict]:
        """The messages for one request: the instructions and the filled-in user message."""
        names = set(_PLACEHOLDER.findall(self.user_template))
        missing = names - values.keys()
        if missing:
            raise ValueError(f"no value for {sorted(missing)} in the {self.step} prompt")
        user = _PLACEHOLDER.sub(lambda m: values[m.group(1)], self.user_template)
        return [{"role": "system", "content": self.system}, {"role": "user", "content": user}]


def load_prompt(step: str, version: str, root: Path = PROMPTS_DIR) -> Prompt:
    folder = root / step / version
    if not folder.is_dir():
        raise SystemExit(f"prompt folder {folder} does not exist")
    files = [folder / "system.md", folder / "user.md", folder / "output.schema.json"]
    digest = hashlib.sha256()
    for f in files:
        digest.update(f.read_bytes())
    return Prompt(step=step, version=version,
                  system=files[0].read_text(encoding="utf-8"),
                  user_template=files[1].read_text(encoding="utf-8"),
                  schema=json.loads(files[2].read_text(encoding="utf-8")),
                  sha256=digest.hexdigest())
