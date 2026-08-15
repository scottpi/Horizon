"""Batched localization for the "In Kürze" short-items section.

Short items skip full per-item enrichment to keep cost down; instead this
does a single combined translation call for the whole batch.
"""

import logging
from typing import Dict, List, Tuple

from .client import AIClient
from .utils import parse_json_response
from ..models import ContentItem

logger = logging.getLogger(__name__)

MAX_SUMMARY_CHARS = 400


def _target_language_instruction(language: str) -> str:
    if language.lower() == "zh":
        return "Simplified Chinese (language tag `zh`)"
    return f"language `{language}`"


async def localize_short_items(
    items: List[ContentItem],
    language: str,
    client: AIClient,
) -> Dict[str, Tuple[str, str]]:
    """Return {item_id: (title, summary)} localized in one batched call.

    On any failure, returns an empty dict; callers should fall back to the
    item's original (untranslated) title/summary.
    """
    if not items or language.lower() == "en":
        return {}

    entries = []
    for item in items:
        analysis = item.processing.analysis if item.processing else None
        summary = (analysis.summary if analysis else "") or ""
        entries.append(
            f'- id: "{item.id}"\n'
            f"  title: {item.title}\n"
            f"  summary: {summary[:MAX_SUMMARY_CHARS]}"
        )

    system = (
        "You localize short news blurbs for a newspaper's brief-items section. "
        f"Write every title and summary in {_target_language_instruction(language)}. "
        "Keep each summary to one short, factual sentence. Do not add commentary, "
        "opinions, or information not present in the source. Preserve concrete "
        "names, numbers, and organizations."
    )
    user = (
        "Localize each item below. Return valid JSON only:\n"
        '{"items": [{"id": "<exact id>", "title": "<localized short title>", '
        '"summary": "<localized one-sentence summary>"}]}\n\n' + "\n".join(entries)
    )

    try:
        response = await client.complete(system=system, user=user)
    except Exception as e:
        logger.warning("Short-item localization request failed: %s", e)
        return {}

    parsed = parse_json_response(response)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("items"), list):
        logger.warning("Short-item localization returned an unexpected shape")
        return {}

    valid_ids = {item.id for item in items}
    result: Dict[str, Tuple[str, str]] = {}
    for entry in parsed["items"]:
        if not isinstance(entry, dict):
            continue
        item_id = entry.get("id")
        title = entry.get("title")
        summary = entry.get("summary")
        if item_id in valid_ids and isinstance(title, str) and isinstance(summary, str):
            result[item_id] = (title.strip(), summary.strip())
    return result
