"""Access to the research thread's curriculum.json (stages, concept graph, scheduler defaults).

`piano-companion-seed` copies the file into the data dir, so the Pi does not depend on the research
folder at runtime. Everything here degrades to built-in defaults when the file is absent.
"""

import json
from functools import lru_cache
from pathlib import Path

from .config import get_settings

FILENAME = "curriculum.json"


def path() -> Path:
    return get_settings().data_dir / FILENAME


@lru_cache
def load() -> dict:
    p = path()
    return json.loads(p.read_text()) if p.is_file() else {}


def scheduler_defaults() -> dict:
    return load().get("scheduler_defaults", {})


def reload() -> None:
    load.cache_clear()
