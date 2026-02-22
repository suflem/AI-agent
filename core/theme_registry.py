from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

THEME_FILE = Path(__file__).resolve().parent.parent / "frontend" / "src" / "theme" / "opencode_themes.json"
PREF_FILE = Path(__file__).resolve().parent.parent / "memories" / "ui_preferences.json"


def _default_registry() -> dict[str, Any]:
    return {
        "version": 1,
        "default_theme": "opencode_night",
        "themes": [],
    }


def load_theme_registry() -> dict[str, Any]:
    try:
        with THEME_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("themes"), list):
            return data
    except Exception:
        pass
    return _default_registry()


def _theme_map(registry: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    data = registry or load_theme_registry()
    items = data.get("themes")
    if not isinstance(items, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if name:
            out[name] = item
    return out


def list_theme_names() -> list[str]:
    return sorted(_theme_map().keys())


def list_themes_for_cli() -> list[str]:
    rows = []
    for item in load_theme_registry().get("themes", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        label = str(item.get("label", "")).strip()
        variant = str(item.get("variant", "dark")).strip()
        if name:
            rows.append(f"{name} ({variant}) {label}")
    return rows


def get_theme(name: str | None = None) -> dict[str, Any] | None:
    registry = load_theme_registry()
    mapping = _theme_map(registry)
    key = str(name or "").strip()
    if not key:
        key = str(registry.get("default_theme", "opencode_night"))
    if key in mapping:
        return mapping[key]
    return mapping.get(str(registry.get("default_theme", "opencode_night")))


def _load_prefs() -> dict[str, Any]:
    if not PREF_FILE.exists():
        return {}
    try:
        with PREF_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}


def _save_prefs(data: dict[str, Any]) -> None:
    PREF_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PREF_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_active_theme_name(surface: str = "tui") -> str:
    env_name = os.getenv("AI_THEME", "").strip()
    if env_name:
        return env_name
    prefs = _load_prefs()
    key = f"{surface}_theme"
    stored = str(prefs.get(key, "")).strip()
    if stored:
        return stored
    registry = load_theme_registry()
    return str(registry.get("default_theme", "opencode_night"))


def set_active_theme_name(name: str, surface: str = "tui") -> tuple[bool, str]:
    theme = get_theme(name)
    if not theme:
        return False, ""
    resolved = str(theme.get("name", "")).strip()
    if not resolved:
        return False, ""
    prefs = _load_prefs()
    prefs[f"{surface}_theme"] = resolved
    _save_prefs(prefs)
    return True, resolved
