"""
Límites y truncado del payload de historial.

Motivación:
- Al extraer “todo lo visible” (incluyendo HTML), el tamaño puede crecer mucho.
- Postgres JSON soporta documentos grandes, pero conviene mantener límites para:
  - evitar latencias enormes
  - evitar exceder límites de request/response y memoria
  - mantener UX razonable en frontend
"""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple


def _truncate_str(s: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    return s if len(s) <= max_chars else (s[:max_chars] + "…(truncado)")


def _safe_json_size(obj: Any) -> int:
    """
    Tamaño aproximado del objeto serializado a JSON UTF-8.
    """
    try:
        return len(json.dumps(obj, ensure_ascii=False).encode("utf-8"))
    except Exception:
        return 0


def enforce_workout_limits(
    workout: Dict[str, Any],
    *,
    max_visible_text_chars: int = 20_000,
    max_html_sections: int = 3,
    max_html_chars_per_section: int = 50_000,
    max_workout_bytes: int = 250_000
) -> Tuple[Dict[str, Any], bool]:
    """
    Aplica límites a un workout individual (in-place safe via copy superficial).

    Estrategia:
    - Truncar `full_details.visible_text`
    - Limitar cantidad de `html_sections` y truncar su HTML
    - Si aún excede `max_workout_bytes`, eliminar `html_sections`

    Returns:
        (workout_limited, was_modified)
    """
    was_modified = False
    w = dict(workout)
    fd = w.get("full_details")
    if isinstance(fd, dict):
        fd2 = dict(fd)

        vt = fd2.get("visible_text")
        if isinstance(vt, str):
            new_vt = _truncate_str(vt, max_visible_text_chars)
            if new_vt != vt:
                fd2["visible_text"] = new_vt
                was_modified = True

        hs = fd2.get("html_sections")
        if isinstance(hs, list):
            new_sections = []
            for sec in hs[:max_html_sections]:
                if not isinstance(sec, dict):
                    continue
                sec2 = dict(sec)
                oh = sec2.get("outer_html")
                if isinstance(oh, str):
                    new_oh = _truncate_str(oh, max_html_chars_per_section)
                    if new_oh != oh:
                        sec2["outer_html"] = new_oh
                        was_modified = True
                new_sections.append(sec2)
            if new_sections != hs:
                fd2["html_sections"] = new_sections
                was_modified = True

        w["full_details"] = fd2

    if _safe_json_size(w) > max_workout_bytes:
        fd = w.get("full_details")
        if isinstance(fd, dict) and "html_sections" in fd:
            fd2 = dict(fd)
            fd2.pop("html_sections", None)
            w["full_details"] = fd2
            was_modified = True

    return w, was_modified


