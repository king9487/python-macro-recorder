from __future__ import annotations

import json
from pathlib import Path

from .models import Macro, MacroValidationError


def load_macro(path: str | Path) -> Macro:
    try:
        with Path(path).open("r", encoding="utf-8") as stream:
            return Macro.from_dict(json.load(stream))
    except json.JSONDecodeError as exc:
        raise MacroValidationError(f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    except OSError as exc:
        raise MacroValidationError(f"Could not read the macro file: {exc}") from exc


def save_macro(macro: Macro, path: str | Path) -> None:
    target = Path(path)
    try:
        with target.open("w", encoding="utf-8") as stream:
            json.dump(macro.to_dict(), stream, indent=2, ensure_ascii=False)
            stream.write("\n")
    except OSError as exc:
        raise MacroValidationError(f"Could not save the macro file: {exc}") from exc
