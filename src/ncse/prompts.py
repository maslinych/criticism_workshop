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
    sha256: str  # checksum of the prompt files, recorded with every request
    part_template: str | None = None  # user-part.md: the message for one part of a long article (D-034)

    def render(self, part: bool = False, **values: str) -> list[dict]:
        """The messages for one request: the instructions and the filled-in user
        message (for one part of a long article if `part`)."""
        template = self.user_template
        if part:
            if self.part_template is None:
                raise SystemExit(f"prompt {self.step}/{self.version} has no user-part.md, so it cannot be "
                                 "used for long articles sent in parts (D-034)")
            template = self.part_template
        names = set(_PLACEHOLDER.findall(template))
        missing = names - values.keys()
        if missing:
            raise ValueError(f"no value for {sorted(missing)} in the {self.step} prompt")
        user = _PLACEHOLDER.sub(lambda m: values[m.group(1)], template)
        return [{"role": "system", "content": self.system}, {"role": "user", "content": user}]


def load_prompt(step: str, version: str, root: Path = PROMPTS_DIR) -> Prompt:
    folder = root / step / version
    if not folder.is_dir():
        raise SystemExit(f"prompt folder {folder} does not exist")
    files = [folder / "system.md", folder / "user.md", folder / "output.schema.json"]
    part = folder / "user-part.md"  # optional; older versions have none
    digest = hashlib.sha256()
    for f in files + ([part] if part.exists() else []):
        digest.update(f.read_bytes())
    return Prompt(step=step, version=version,
                  system=files[0].read_text(encoding="utf-8"),
                  user_template=files[1].read_text(encoding="utf-8"),
                  schema=json.loads(files[2].read_text(encoding="utf-8")),
                  sha256=digest.hexdigest(),
                  part_template=part.read_text(encoding="utf-8") if part.exists() else None)
