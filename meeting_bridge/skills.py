from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re

import yaml


SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


@dataclass(frozen=True)
class Skill:
    skill_id: str
    name: str
    description: str
    triggers: tuple[str, ...]
    task_types: tuple[str, ...]
    body: str
    path: Path


def _parse_skill(path: Path) -> Skill | None:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return None

    meta: dict = {}
    body = text

    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0:
            raw_meta = text[4:end]
            body = text[end + 5:].strip()
            loaded = yaml.safe_load(raw_meta) or {}
            if isinstance(loaded, dict):
                meta = loaded

    skill_id = str(meta.get("id") or path.parent.name).strip()
    name = str(meta.get("name") or skill_id).strip()
    description = str(meta.get("description") or "").strip()

    raw_triggers = meta.get("triggers") or []
    if isinstance(raw_triggers, str):
        raw_triggers = [raw_triggers]

    triggers = tuple(
        str(item).strip().casefold()
        for item in raw_triggers
        if str(item).strip()
    )

    raw_task_types = meta.get("task_types") or []
    if isinstance(raw_task_types, str):
        raw_task_types = [raw_task_types]

    task_types = tuple(
        str(item).strip().casefold()
        for item in raw_task_types
        if str(item).strip()
    )

    return Skill(
        skill_id=skill_id,
        name=name,
        description=description,
        triggers=triggers,
        task_types=task_types,
        body=body,
        path=path,
    )


@lru_cache(maxsize=1)
def load_skills() -> tuple[Skill, ...]:
    if not SKILLS_DIR.exists():
        return ()

    result: list[Skill] = []

    for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        try:
            skill = _parse_skill(path)
        except Exception:
            continue

        if skill is not None:
            result.append(skill)

    return tuple(result)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.casefold(), flags=re.UNICODE))


def _contains_token(text: str, token: str) -> bool:
    return token.casefold() in _tokens(text)


def _trigger_matches(haystack: str, trigger: str) -> bool:
    """Short abbreviations match only as standalone tokens."""
    if not trigger:
        return False

    if len(trigger) <= 3 and trigger.isalnum():
        return _contains_token(haystack, trigger)

    return trigger in haystack


def infer_task_types(text: str) -> frozenset[str]:
    """
    Infer the kind of analyst task before selecting procedural skills.

    This intentionally uses stronger semantic signals than ordinary
    skill triggers. A generic word such as "process" must not activate
    a large requirements skill by itself.
    """
    h = (text or "").casefold()
    if not h.strip():
        return frozenset()

    result: set[str] = set()
    tokens = _tokens(h)

    # ------------------------------------------------------------
    # ACCOUNTING
    # ------------------------------------------------------------

    accounting_short_tokens = {
        "\u0431\u0443",      # ??
        "\u043d\u0443",      # ??
        "\u043d\u0434\u0441",
        "\u043f\u043d\u043e",
        "\u043f\u043d\u0430",
        "\u043e\u043d\u043e",
        "\u043e\u043d\u0430",
    }

    accounting_markers = (
        "\u043d\u0430\u043b\u043e\u0433 \u043d\u0430 \u043f\u0440\u0438\u0431\u044b\u043b\u044c",
        "\u0432\u0445\u043e\u0434\u043d\u043e\u0439 \u043d\u0434\u0441",
        "\u0430\u0432\u0430\u043d\u0441\u043e\u0432\u044b\u0439 \u043d\u0434\u0441",
        "\u043a\u043d\u0438\u0433\u0430 \u043f\u043e\u043a\u0443\u043f\u043e\u043a",
        "\u043a\u043d\u0438\u0433\u0430 \u043f\u0440\u043e\u0434\u0430\u0436",
        "\u0432\u044b\u0447\u0435\u0442 \u043d\u0434\u0441",
        "\u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u043d\u0434\u0441",
        "\u0432\u0440\u0435\u043c\u0435\u043d\u043d\u0430\u044f \u0440\u0430\u0437\u043d\u0438\u0446",
        "\u043f\u043e\u0441\u0442\u043e\u044f\u043d\u043d\u0430\u044f \u0440\u0430\u0437\u043d\u0438\u0446",
        "\u043d\u0430\u043b\u043e\u0433\u043e\u0432\u044b\u0439 \u0443\u0447\u0435\u0442",
        "\u0431\u0443\u0445\u0433\u0430\u043b\u0442\u0435\u0440\u0441\u043a\u0438\u0439 \u0443\u0447\u0435\u0442",
        "profit tax",
        "vat",
    )

    if (
        accounting_short_tokens.intersection(tokens)
        or any(marker in h for marker in accounting_markers)
    ):
        result.add("accounting")

    # ------------------------------------------------------------
    # DIAGNOSIS
    # ------------------------------------------------------------

    diagnosis_strong = (
        "\u043e\u0448\u0438\u0431\u043a",
        "\u0440\u0430\u0441\u0445\u043e\u0436\u0434",
        "\u043d\u0435 \u0441\u0445\u043e\u0434",
        "\u043d\u0435 \u0437\u0430\u043f\u043e\u043b\u043d",
        "\u043d\u0435 \u043e\u0442\u0440\u0430\u0436",
        "\u043d\u0435\u0432\u0435\u0440\u043d",
        "\u0447\u0442\u043e \u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c",
        "\u043a\u0430\u043a \u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c",
        "\u0434\u0438\u0430\u0433\u043d\u043e\u0441\u0442",
        "\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440",
        "\u0434\u0432\u0438\u0436\u0435\u043d\u0438\u044f \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442",
        "\u0437\u0430\u043a\u0440\u044b\u0442\u0438\u0435 \u043c\u0435\u0441\u044f\u0446\u0430",
        "root cause",
        "diagnos",
        "reconcile",
    )

    diagnosis_domain = (
        "1\u0441",
        "erp",
        "\u0443\u0447\u0435\u0442",
        "\u043e\u0442\u0447\u0435\u0442",
        "\u043e\u0442\u0447\u0451\u0442",
        "\u0440\u0435\u0433\u0438\u0441\u0442\u0440",
        "\u043f\u0440\u043e\u0432\u043e\u0434\u043a",
        "\u0441\u0435\u0431\u0435\u0441\u0442\u043e\u0438\u043c",
        "\u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442",
        "\u043d\u0434\u0441",
        "\u0431\u0443",
        "\u043d\u0443",
        "\u043d\u0430\u043b\u043e\u0433",
        "\u0441\u043a\u043b\u0430\u0434",
        "\u043f\u0440\u043e\u0438\u0437\u0432\u043e\u0434\u0441\u0442\u0432",
    )

    has_strong_diagnosis = any(
        marker in h for marker in diagnosis_strong
    )

    has_why_in_domain = (
        "\u043f\u043e\u0447\u0435\u043c\u0443" in h
        and any(marker in h for marker in diagnosis_domain)
    )

    has_cause_in_domain = (
        "\u043f\u0440\u0438\u0447\u0438\u043d" in h
        and any(marker in h for marker in diagnosis_domain)
    )

    if has_strong_diagnosis or has_why_in_domain or has_cause_in_domain:
        result.add("diagnosis")

    # ------------------------------------------------------------
    # REQUIREMENTS
    # ------------------------------------------------------------

    requirements_strong = (
        "\u0442\u0440\u0435\u0431\u043e\u0432\u0430\u043d",
        "\u0431\u0438\u0437\u043d\u0435\u0441-\u0442\u0440\u0435\u0431\u043e\u0432\u0430\u043d",
        "\u043f\u043e\u0441\u0442\u0430\u043d\u043e\u0432\u043a",
        "\u0442\u0435\u0445\u043d\u0438\u0447\u0435\u0441\u043a\u043e\u0435 \u0437\u0430\u0434\u0430\u043d\u0438\u0435",
        "\u043a\u0440\u0438\u0442\u0435\u0440\u0438\u0438 \u043f\u0440\u0438\u0435\u043c\u043a",
        "\u043a\u0440\u0438\u0442\u0435\u0440\u0438\u0438 \u043f\u0440\u0438\u0451\u043c\u043a",
        "\u043e\u0431\u0441\u043b\u0435\u0434\u043e\u0432\u0430\u043d",
        "as-is",
        "to-be",
        "gap",
    )

    if (
        any(marker in h for marker in requirements_strong)
        or "??" in tokens
    ):
        result.add("requirements")
    else:
        requirements_change = (
            "\u0434\u043e\u0440\u0430\u0431\u043e\u0442",
            "\u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0437",
            "\u0438\u043d\u0442\u0435\u0433\u0440\u0430\u0446",
            "\u0438\u043d\u0442\u0435\u0433\u0440\u0438\u0440",
            "\u0440\u0435\u0430\u043b\u0438\u0437\u043e\u0432\u0430\u0442",
            "\u0438\u0437\u043c\u0435\u043d\u0438\u0442\u044c \u043f\u0440\u043e\u0446\u0435\u0441\u0441",
        )

        requirements_context = (
            "\u0437\u0430\u043a\u0430\u0437\u0447\u0438\u043a",
            "\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b",
            "\u0431\u0438\u0437\u043d\u0435\u0441",
            "\u043d\u0430 \u0432\u0441\u0442\u0440\u0435\u0447\u0435",
            "1\u0441",
            "erp",
            "\u043f\u0440\u043e\u0446\u0435\u0441\u0441",
        )

        if (
            any(marker in h for marker in requirements_change)
            and any(marker in h for marker in requirements_context)
        ):
            result.add("requirements")

    # ------------------------------------------------------------
    # REPORT ANALYSIS / DRILLDOWN
    # ------------------------------------------------------------

    reporting_educational = (
        h.strip().startswith(
            "\u0447\u0442\u043e \u0442\u0430\u043a\u043e\u0435 \u043e\u0441\u0432"
        )
        or h.strip().startswith(
            "\u0447\u0442\u043e \u0442\u0430\u043a\u043e\u0435 \u043e\u0442\u0447\u0451\u0442"
        )
        or h.strip().startswith(
            "\u0447\u0442\u043e \u0442\u0430\u043a\u043e\u0435 \u043e\u0442\u0447\u0435\u0442"
        )
    )

    reporting_strong = (
        "\u043e\u0442\u043a\u0443\u0434\u0430 \u0446\u0438\u0444\u0440\u0430 \u0432 \u043e\u0442\u0447\u0435\u0442",
        "\u043e\u0442\u043a\u0443\u0434\u0430 \u0441\u0443\u043c\u043c\u0430 \u0432 \u043e\u0442\u0447\u0451\u0442",
        "\u043e\u0442\u043a\u0443\u0434\u0430 \u0441\u0442\u0440\u043e\u043a\u0430 \u0432 \u043e\u0442\u0447\u0451\u0442",
        "\u0440\u0430\u0441\u0448\u0438\u0444\u0440\u043e\u0432\u043a\u0430 \u043e\u0442\u0447\u0451\u0442",
        "\u0440\u0430\u0441\u0448\u0438\u0444\u0440\u043e\u0432\u043a\u0430 \u043e\u0442\u0447\u0435\u0442",
        "\u043d\u0435 \u0441\u0445\u043e\u0434\u044f\u0442\u0441\u044f \u043e\u0442\u0447\u0451\u0442",
        "\u043d\u0435 \u0441\u0445\u043e\u0434\u044f\u0442\u0441\u044f \u043e\u0442\u0447\u0435\u0442",
        "\u0440\u0430\u0437\u043d\u044b\u0435 \u0446\u0438\u0444\u0440\u044b \u0432 \u043e\u0442\u0447\u0451\u0442",
        "\u043e\u0441\u0432 \u043d\u0435 \u0441\u0445\u043e\u0434\u0438\u0442",
        "report drilldown",
        "report discrepancy",
    )

    report_object = (
        "\u043e\u0442\u0447\u0451\u0442",
        "\u043e\u0442\u0447\u0435\u0442",
        "\u043e\u0441\u0432",
        "\u0432\u0435\u0434\u043e\u043c\u043e\u0441\u0442",
        "\u043a\u043d\u0438\u0433\u0430 \u043f\u043e\u043a\u0443\u043f\u043e\u043a",
        "\u043a\u043d\u0438\u0433\u0430 \u043f\u0440\u043e\u0434\u0430\u0436",
    )

    report_investigation = (
        "\u043e\u0442\u043a\u0443\u0434\u0430" in h
        or "\u0440\u0430\u0441\u0448\u0438\u0444\u0440" in h
        or "\u043f\u043e\u0447\u0435\u043c\u0443" in h
        or "\u043d\u0435 \u0441\u0445\u043e\u0434" in h
        or "\u0440\u0430\u0441\u0445\u043e\u0436\u0434" in h
        or "\u043d\u0435 \u0441\u043e\u0432\u043f\u0430\u0434" in h
        or "\u0440\u0430\u0437\u043d\u0438\u0446" in h
    )

    has_report_investigation = (
        any(marker in h for marker in report_object)
        and report_investigation
    )

    if (
        not reporting_educational
        and (
            any(marker in h for marker in reporting_strong)
            or has_report_investigation
        )
    ):
        result.add("reporting")

    # ------------------------------------------------------------
    # DOCUMENT MOVEMENTS / DOCUMENT FLOW
    # ------------------------------------------------------------

    movements_educational = (
        h.strip().startswith(
            "\u0447\u0442\u043e \u0442\u0430\u043a\u043e\u0435 \u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440"
        )
        or h.strip().startswith(
            "\u0447\u0442\u043e \u0442\u0430\u043a\u043e\u0435 \u0434\u0432\u0438\u0436\u0435\u043d\u0438\u0435 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430"
        )
    )

    movements_strong = (
        "\u0434\u0432\u0438\u0436\u0435\u043d\u0438\u044f \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430",
        "\u043a\u0430\u043a\u0438\u0435 \u0434\u0432\u0438\u0436\u0435\u043d\u0438\u044f",
        "\u0434\u0432\u0438\u0436\u0435\u043d\u0438\u044f \u043f\u043e \u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u043c",
        "\u043f\u0440\u043e\u0432\u043e\u0434\u043a\u0438 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430",
        "\u043a\u0430\u043a\u0438\u0435 \u043f\u0440\u043e\u0432\u043e\u0434\u043a\u0438",
        "\u043a\u0430\u043a\u043e\u0439 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442 \u0444\u043e\u0440\u043c\u0438\u0440\u0443\u0435\u0442",
        "\u0447\u0442\u043e \u0444\u043e\u0440\u043c\u0438\u0440\u0443\u0435\u0442 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442",
        "\u043a\u0430\u043a\u043e\u0439 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442 \u0441\u043e\u0437\u0434\u0430\u0435\u0442\u0441\u044f",
        "\u0447\u0442\u043e \u0441\u043e\u0437\u0434\u0430\u0435\u0442\u0441\u044f \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438",
        "\u0447\u0442\u043e \u0441\u043e\u0437\u0434\u0430\u0435\u0442\u0441\u044f \u043d\u0430 \u043e\u0441\u043d\u043e\u0432\u0430\u043d\u0438\u0438",
        "\u043e\u0442\u043a\u0443\u0434\u0430 \u0432\u0437\u044f\u043b\u0430\u0441\u044c \u0437\u0430\u043f\u0438\u0441\u044c",
        "\u043e\u0442\u043a\u0443\u0434\u0430 \u0432\u0437\u044f\u043b\u0430\u0441\u044c \u043f\u0440\u043e\u0432\u043e\u0434\u043a\u0430",
        "\u0446\u0435\u043f\u043e\u0447\u043a\u0430 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u043e\u0432",
        "document movements",
        "register movements",
    )

    registrar_context = (
        "\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440" in h
        and (
            "1\u0441" in h
            or "erp" in h
            or "\u0440\u0435\u0433\u0438\u0441\u0442\u0440" in h
            or "\u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442" in h
            or "\u0434\u0432\u0438\u0436\u0435\u043d" in h
            or "\u043f\u0440\u043e\u0432\u043e\u0434\u043a" in h
        )
    )

    document_chain_context = (
        (
            "\u0447\u0442\u043e \u0441\u043e\u0437\u0434\u0430" in h
            or "\u043a\u0430\u043a\u043e\u0439 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442" in h
            or "\u043d\u0430 \u043e\u0441\u043d\u043e\u0432\u0430\u043d\u0438\u0438" in h
        )
        and (
            "1\u0441" in h
            or "erp" in h
            or "\u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442" in h
        )
    )

    if (
        not movements_educational
        and (
            any(marker in h for marker in movements_strong)
            or registrar_context
            or document_chain_context
        )
    ):
        result.add("movements")

    # ------------------------------------------------------------
    # MONTH-END CLOSING / COST CALCULATION
    # ------------------------------------------------------------

    closing_educational = (
        "\u0447\u0442\u043e \u0442\u0430\u043a\u043e\u0435 \u0437\u0430\u043a\u0440\u044b\u0442\u0438\u0435 \u043c\u0435\u0441\u044f\u0446\u0430" in h
        or "\u0447\u0442\u043e \u0442\u0430\u043a\u043e\u0435 \u043d\u0437\u043f" in h
    )

    closing_strong = (
        "\u0437\u0430\u043a\u0440\u044b\u0442\u0438\u0435 \u043c\u0435\u0441\u044f\u0446\u0430",
        "\u0437\u0430\u043a\u0440\u044b\u0442\u044c \u043c\u0435\u0441\u044f\u0446",
        "\u043d\u0435 \u0437\u0430\u043a\u0440\u044b\u0432\u0430\u0435\u0442\u0441\u044f \u043c\u0435\u0441\u044f\u0446",
        "\u043d\u0435 \u0437\u0430\u043a\u0440\u044b\u043b\u0441\u044f \u043c\u0435\u0441\u044f\u0446",
        "\u043f\u0435\u0440\u0435\u0437\u0430\u043a\u0440\u044b\u0442\u0438\u0435 \u043c\u0435\u0441\u044f\u0446\u0430",
        "\u0440\u0430\u0441\u0447\u0435\u0442 \u0441\u0435\u0431\u0435\u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u0438",
        "\u0440\u0430\u0441\u0447\u0451\u0442 \u0441\u0435\u0431\u0435\u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u0438",
        "\u0441\u0435\u0431\u0435\u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c \u043f\u043e\u0441\u043b\u0435 \u0437\u0430\u043a\u0440\u044b\u0442\u0438\u044f",
        "\u0440\u0430\u0441\u043f\u0440\u0435\u0434\u0435\u043b\u0435\u043d\u0438\u0435 \u0440\u0430\u0441\u0445\u043e\u0434\u043e\u0432",
        "\u0437\u0430\u043a\u0440\u044b\u0442\u0438\u0435 \u0437\u0430\u0442\u0440\u0430\u0442",
        "month end closing",
        "period close",
    )

    closing_domain = (
        "1\u0441",
        "erp",
        "\u0431\u0443\u0445",
        "\u0443\u0447\u0435\u0442",
        "\u0437\u0430\u0442\u0440\u0430\u0442",
        "\u0441\u0435\u0431\u0435\u0441\u0442\u043e\u0438\u043c",
        "\u043f\u0440\u043e\u0438\u0437\u0432\u043e\u0434",
        "\u0440\u0430\u0441\u043f\u0440\u0435\u0434\u0435\u043b",
        "\u0440\u0435\u0433\u043b\u0430\u043c\u0435\u043d\u0442\u043d",
    )

    closing_problem = (
        "\u043d\u0435 \u0437\u0430\u043a\u0440\u044b",
        "\u043e\u0448\u0438\u0431",
        "\u043d\u0435 \u0440\u0430\u0441\u0441\u0447\u0438\u0442",
        "\u043d\u0435 \u0440\u0430\u0441\u043f\u0440\u0435\u0434",
        "\u043d\u0435 \u0441\u043f\u0438\u0441",
        "\u043f\u043e\u0441\u043b\u0435 \u0437\u0430\u043a\u0440\u044b\u0442",
        "\u043f\u043e\u0441\u043b\u0435 \u043f\u0435\u0440\u0435\u0437\u0430\u043a\u0440\u044b\u0442",
    )

    has_closing_strong = any(
        marker in h for marker in closing_strong
    )

    has_closing_problem = (
        any(marker in h for marker in closing_problem)
        and any(marker in h for marker in closing_domain)
    )

    # N?? by itself is relevant only in an accounting/production context.
    has_wip_context = (
        (
            _contains_token(h, "\u043d\u0437\u043f")
            or "\u043d\u0435\u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u043d\u043e\u0435 \u043f\u0440\u043e\u0438\u0437\u0432\u043e\u0434\u0441\u0442\u0432\u043e" in h
            or "\u043d\u0435\u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043d\u043d\u043e\u0435 \u043f\u0440\u043e\u0438\u0437\u0432\u043e\u0434\u0441\u0442\u0432\u043e" in h
        )
        and any(marker in h for marker in closing_domain)
    )

    if (
        not closing_educational
        and (
            has_closing_strong
            or has_closing_problem
            or has_wip_context
        )
    ):
        result.add("closing")

    # ------------------------------------------------------------
    # DATA RECONCILIATION / CONSISTENCY
    # ------------------------------------------------------------

    # Educational questions must not activate a large procedural skill.
    reconciliation_educational = (
        "\u0447\u0442\u043e \u0442\u0430\u043a\u043e\u0435 \u0441\u0432\u0435\u0440\u043a\u0430" in h
        or "\u0447\u0442\u043e \u0437\u043d\u0430\u0447\u0438\u0442 \u0441\u0432\u0435\u0440\u043a\u0430" in h
        or "\u043e\u0431\u044a\u044f\u0441\u043d\u0438, \u0447\u0442\u043e \u0442\u0430\u043a\u043e\u0435 \u0441\u0432\u0435\u0440\u043a\u0430" in h
        or "\u0447\u0442\u043e \u0442\u0430\u043a\u043e\u0435 reconciliation" in h
    )

    reconciliation_strong = (
        "\u0441\u0432\u0435\u0440\u043a\u0430 \u0434\u0430\u043d\u043d\u044b\u0445",
        "\u0441\u0432\u0435\u0440\u043a\u0430 1\u0441",
        "\u0441\u0432\u0435\u0440\u043a\u0430 sap",
        "\u0441\u0432\u0435\u0440\u043a\u0430 excel",
        "\u0441\u0432\u0435\u0440\u0438\u0442\u044c 1\u0441",
        "\u0441\u0432\u0435\u0440\u0438\u0442\u044c \u0441 sap",
        "\u0441\u0432\u0435\u0440\u0438\u0442\u044c \u0441 excel",
        "\u043a\u043e\u043d\u0441\u0438\u0441\u0442\u0435\u043d\u0442\u043d\u043e\u0441\u0442\u044c",
        "\u0441\u043e\u043f\u043e\u0441\u0442\u0430\u0432\u043b\u0435\u043d\u0438\u0435 \u0434\u0430\u043d\u043d\u044b\u0445",
        "reconciliation",
        "data consistency",
    )

    reconciliation_action = (
        "\u0441\u0432\u0435\u0440\u043a",
        "\u0441\u0432\u0435\u0440\u0438\u0442",
        "\u0441\u043e\u043f\u043e\u0441\u0442\u0430\u0432",
        "\u043c\u044d\u043f\u043f\u0438\u043d\u0433",
        "reconcile",
    )

    reconciliation_system_markers = (
        "1\u0441",
        "sap",
        "excel",
        "erp",
    )

    reconciliation_domain = (
        "\u0434\u0430\u043d\u043d",
        "\u043e\u0441\u0442\u0430\u0442",
        "\u043e\u0431\u043e\u0440\u043e\u0442",
        "\u0441\u0430\u043b\u044c\u0434\u043e",
        "\u043e\u0441\u0432",
        "\u0441\u0447\u0435\u0442",
        "\u0440\u0435\u0433\u0438\u0441\u0442\u0440",
        "\u043e\u0442\u0447\u0435\u0442",
        "\u043e\u0442\u0447\u0451\u0442",
        "\u043f\u0440\u043e\u0432\u043e\u0434\u043a",
    )

    reconciliation_difference = (
        "\u043d\u0435 \u0441\u0445\u043e\u0434",
        "\u0440\u0430\u0441\u0445\u043e\u0436\u0434",
        "\u043e\u0442\u043b\u0438\u0447\u0430",
        "\u0440\u0430\u0437\u043d\u0438\u0446",
        "\u043d\u0435 \u0441\u043e\u0432\u043f\u0430\u0434",
    )

    balance_or_turnover = (
        "\u043e\u0441\u0442\u0430\u0442",
        "\u043e\u0431\u043e\u0440\u043e\u0442",
        "\u0441\u0430\u043b\u044c\u0434\u043e",
        "\u043e\u0441\u0432",
    )

    system_count = sum(
        1
        for marker in reconciliation_system_markers
        if marker in h
    )

    has_strong_reconciliation = any(
        marker in h for marker in reconciliation_strong
    )

    has_reconciliation_action = (
        any(marker in h for marker in reconciliation_action)
        and any(marker in h for marker in reconciliation_domain)
        and (
            system_count >= 1
            or "\u0434\u0430\u043d\u043d" in h
        )
    )

    # Cross-system mismatch may be a reconciliation even when the user
    # never explicitly says "reconcile".
    #
    # Example:
    # "1C and SAP turnovers match, but opening balances do not."
    has_cross_system_difference = (
        system_count >= 2
        and any(marker in h for marker in reconciliation_difference)
        and any(marker in h for marker in balance_or_turnover)
    )

    if (
        not reconciliation_educational
        and (
            has_strong_reconciliation
            or has_reconciliation_action
            or has_cross_system_difference
        )
    ):
        result.add("reconciliation")

    # ------------------------------------------------------------
    # MEETING / LIVE ANALYST
    # ------------------------------------------------------------

    meeting_strong = (
        "\u0432\u043e \u0432\u0440\u0435\u043c\u044f \u0432\u0441\u0442\u0440\u0435\u0447\u0438",
        "\u043d\u0430 \u0441\u043e\u0437\u0432\u043e\u043d\u0435",
        "\u0432\u043e \u0432\u0440\u0435\u043c\u044f \u0441\u043e\u0437\u0432\u043e\u043d\u0430",
        "\u0447\u0442\u043e \u0441\u043f\u0440\u043e\u0441\u0438\u0442\u044c \u0441\u0435\u0439\u0447\u0430\u0441",
        "\u0447\u0442\u043e \u0443\u0442\u043e\u0447\u043d\u0438\u0442\u044c \u0441\u0435\u0439\u0447\u0430\u0441",
        "\u0447\u0442\u043e \u043c\u044b \u0440\u0435\u0448\u0438\u043b\u0438",
        "\u043f\u043e\u0434\u0432\u0435\u0434\u0438 \u0438\u0442\u043e\u0433\u0438 \u0432\u0441\u0442\u0440\u0435\u0447\u0438",
        "\u043f\u043e\u0434\u0432\u0435\u0434\u0438 \u0438\u0442\u043e\u0433\u0438 \u044d\u0442\u043e\u0439 \u0432\u0441\u0442\u0440\u0435\u0447\u0438",
        "\u0438\u0442\u043e\u0433\u0438 \u044d\u0442\u043e\u0439 \u0432\u0441\u0442\u0440\u0435\u0447\u0438",
        "\u0441\u0430\u043c\u043c\u0430\u0440\u0438 \u0432\u0441\u0442\u0440\u0435\u0447\u0438",
        "\u043f\u0440\u043e\u0442\u043e\u043a\u043e\u043b \u0432\u0441\u0442\u0440\u0435\u0447\u0438",
        "\u0438\u0442\u043e\u0433\u0438 \u0441\u043e\u0437\u0432\u043e\u043d\u0430",
        "\u043f\u0440\u043e\u0442\u043e\u043a\u043e\u043b \u0441\u043e\u0437\u0432\u043e\u043d\u0430",
        "meeting summary",
    )

    meeting_work_context = (
        "\u0437\u0430\u043a\u0430\u0437\u0447\u0438\u043a",
        "\u043a\u043b\u0438\u0435\u043d\u0442",
        "\u0430\u043d\u0430\u043b\u0438\u0442\u0438\u043a",
        "\u043a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u043d\u0442",
        "\u043f\u0440\u043e\u0435\u043a\u0442",
        "\u0431\u0438\u0437\u043d\u0435\u0441",
        "1\u0441",
        "erp",
        "sap",
        "\u0442\u0440\u0435\u0431\u043e\u0432\u0430\u043d",
        "\u0434\u043e\u0440\u0430\u0431\u043e\u0442",
        "\u0438\u043d\u0442\u0435\u0433\u0440\u0430\u0446",
        "\u043e\u0448\u0438\u0431\u043a",
        "\u0443\u0447\u0435\u0442",
        "\u043d\u0434\u0441",
    )

    meeting_scene = (
        "\u043d\u0430 \u0432\u0441\u0442\u0440\u0435\u0447\u0435",
        "\u0432\u0441\u0442\u0440\u0435\u0447\u0430",
        "\u0441\u043e\u0437\u0432\u043e\u043d",
    )

    transcript_markers = (
        "\u0441\u0442\u0435\u043d\u043e\u0433\u0440\u0430\u043c\u043c\u0430 \u0432\u0441\u0442\u0440\u0435\u0447\u0438",
        "\u0441\u0442\u0435\u043d\u043e\u0433\u0440\u0430\u043c\u043c\u0430 \u0441\u043e\u0437\u0432\u043e\u043d\u0430",
        "\u0441\u0442\u0435\u043d\u043e\u0433\u0440\u0430\u043c\u043c\u0430 \u0440\u0430\u0437\u0433\u043e\u0432\u043e\u0440\u0430",
    )

    has_meeting_strong = any(
        marker in h for marker in meeting_strong
    )

    has_work_meeting = (
        any(marker in h for marker in meeting_scene)
        and any(marker in h for marker in meeting_work_context)
    )

    has_meeting_transcript = any(
        marker in h for marker in transcript_markers
    )

    if has_meeting_strong or has_work_meeting or has_meeting_transcript:
        result.add("meeting")

    # ------------------------------------------------------------
    # TESTING
    # ------------------------------------------------------------

    testing_markers = (
        "\u0442\u0435\u0441\u0442-\u043a\u0435\u0439\u0441",
        "\u0442\u0435\u0441\u0442 \u043a\u0435\u0439\u0441",
        "\u0442\u0435\u0441\u0442\u043e\u0432\u044b\u0439 \u0441\u0446\u0435\u043d\u0430\u0440",
        "\u0442\u0435\u0441\u0442\u043e\u0432\u044b\u0435 \u0441\u0446\u0435\u043d\u0430\u0440",
        "\u0442\u0435\u0441\u0442\u043e\u0432\u044b\u0445 \u0441\u0446\u0435\u043d\u0430\u0440",
        "\u0441\u0446\u0435\u043d\u0430\u0440\u0438\u0439 \u043f\u0440\u043e\u0432\u0435\u0440\u043a",
        "\u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0434\u043e\u0440\u0430\u0431\u043e\u0442\u043a",
        "\u043f\u0440\u043e\u0442\u0435\u0441\u0442\u0438\u0440\u043e\u0432\u0430\u0442\u044c",
        "\u043f\u0440\u0438\u0435\u043c\u043e\u0447\u043d\u043e\u0435 \u0442\u0435\u0441\u0442\u0438\u0440\u043e\u0432\u0430\u043d",
        "\u043f\u0440\u0438\u0451\u043c\u043e\u0447\u043d\u043e\u0435 \u0442\u0435\u0441\u0442\u0438\u0440\u043e\u0432\u0430\u043d",
        "\u0440\u0435\u0433\u0440\u0435\u0441\u0441\u0438\u043e\u043d\u043d\u043e\u0435 \u0442\u0435\u0441\u0442\u0438\u0440\u043e\u0432\u0430\u043d",
        "test case",
        "acceptance test",
        "regression test",
        "uat",
    )

    testing_acceptance = (
        "\u043a\u0440\u0438\u0442\u0435\u0440\u0438\u0438 \u043f\u0440\u0438\u0435\u043c\u043a" in h
        or "\u043a\u0440\u0438\u0442\u0435\u0440\u0438\u0438 \u043f\u0440\u0438\u0451\u043c\u043a" in h
    )

    if any(marker in h for marker in testing_markers) or testing_acceptance:
        result.add("testing")


    # ------------------------------------------------------------
    # FINAL TASK NORMALIZER V2
    # ------------------------------------------------------------
    #
    # This block runs after all primary classifiers and corrects
    # grammatical / educational boundary cases.

    h_stripped = h.strip()

    # ------------------------------------------------------------
    # 1. Pure educational definition
    # ------------------------------------------------------------

    educational_definition = (
        h_stripped.startswith(
            "\u0447\u0442\u043e \u0442\u0430\u043a\u043e\u0435 "
        )
        or h_stripped.startswith(
            "\u0447\u0442\u043e \u0437\u043d\u0430\u0447\u0438\u0442 "
        )
        or h_stripped.startswith(
            "\u043e\u0431\u044a\u044f\u0441\u043d\u0438, "
            "\u0447\u0442\u043e \u0442\u0430\u043a\u043e\u0435 "
        )
        or h_stripped.startswith(
            "\u043e\u0431\u044a\u044f\u0441\u043d\u0438 "
            "\u0447\u0442\u043e \u0442\u0430\u043a\u043e\u0435 "
        )
    )

    # ------------------------------------------------------------
    # 2. Explicit diagnostic intent
    # ------------------------------------------------------------

    explicit_diagnostic_intent = (
        "\u043f\u043e\u0447\u0435\u043c\u0443" in h
        or "\u043e\u0448\u0438\u0431" in h
        or "\u043d\u0435 \u0441\u0445\u043e\u0434" in h
        or "\u0440\u0430\u0441\u0445\u043e\u0436\u0434" in h
        or "\u043d\u0435 \u0440\u0430\u0431\u043e\u0442" in h
        or "\u043d\u0435 \u0437\u0430\u043a\u0440\u044b" in h
        or "\u043d\u0435\u0432\u0435\u0440\u043d" in h
        or "\u043f\u0440\u0438\u0447\u0438\u043d" in h
        or "\u0447\u0442\u043e \u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c" in h
        or "\u043a\u0430\u043a \u0438\u0441\u043f\u0440\u0430\u0432" in h
    )

    # ------------------------------------------------------------
    # 3. Month-closing grammatical forms
    # ------------------------------------------------------------

    closing_forms = (
        "\u0437\u0430\u043a\u0440\u044b\u0442\u0438\u0435 \u043c\u0435\u0441\u044f\u0446\u0430",
        "\u0437\u0430\u043a\u0440\u044b\u0442\u0438\u0438 \u043c\u0435\u0441\u044f\u0446\u0430",
        "\u0437\u0430\u043a\u0440\u044b\u0442\u0438\u044f \u043c\u0435\u0441\u044f\u0446\u0430",
        "\u0437\u0430\u043a\u0440\u044b\u0442\u044c \u043c\u0435\u0441\u044f\u0446",
        "\u043f\u0435\u0440\u0435\u0437\u0430\u043a\u0440\u044b\u0442\u0438\u0435",
        "\u043f\u0435\u0440\u0435\u0437\u0430\u043a\u0440\u044b\u0442\u0438\u044f",
    )

    has_closing_form = any(
        marker in h
        for marker in closing_forms
    )

    # Work/accounting context around month closing.
    closing_context = (
        "1\u0441" in h
        or "erp" in h
        or _contains_token(h, "\u0431\u0443")
        or _contains_token(h, "\u043d\u0443")
        or _contains_token(h, "\u043d\u0437\u043f")
        or "\u0441\u0435\u0431\u0435\u0441\u0442\u043e\u0438\u043c" in h
        or "\u0430\u043c\u043e\u0440\u0442\u0438\u0437" in h
        or "\u0437\u0430\u0442\u0440\u0430\u0442" in h
        or "\u043f\u0440\u043e\u0438\u0437\u0432\u043e\u0434" in h
        or "\u0443\u0447\u0435\u0442" in h
        or "\u043e\u0448\u0438\u0431" in h
    )

    # "??? ???????? ??????..."
    # "?????? ???????? ??????..."
    #
    # These must activate the closing skill even when the earlier
    # classifier missed a grammatical form.
    if (
        has_closing_form
        and (
            closing_context
            or explicit_diagnostic_intent
        )
        and not (
            educational_definition
            and not explicit_diagnostic_intent
        )
    ):
        result.add("closing")

    # ------------------------------------------------------------
    # 4. Pure "what is X?" questions
    # ------------------------------------------------------------

    # A pure definition question should not load heavy diagnosis
    # or closing skills.
    if (
        educational_definition
        and not explicit_diagnostic_intent
    ):
        result.discard("diagnosis")
        result.discard("closing")

    # ------------------------------------------------------------
    # 5. Do not invent accounting contour from generic closing error
    # ------------------------------------------------------------

    explicit_accounting_contour = (
        _contains_token(h, "\u0431\u0443")
        or _contains_token(h, "\u043d\u0443")
        or _contains_token(h, "\u043d\u0434\u0441")
        or "\u043d\u0430\u043b\u043e\u0433 \u043d\u0430 \u043f\u0440\u0438\u0431\u044b\u043b\u044c" in h
        or "\u043d\u0430\u043b\u043e\u0433\u043e\u0432\u044b\u0439 \u0443\u0447\u0435\u0442" in h
        or "\u0431\u0443\u0445\u0433\u0430\u043b\u0442\u0435\u0440\u0441\u043a\u0438\u0439 \u0443\u0447\u0435\u0442" in h
        or "\u043a\u043d\u0438\u0433\u0430 \u043f\u043e\u043a\u0443\u043f\u043e\u043a" in h
        or "\u043a\u043d\u0438\u0433\u0430 \u043f\u0440\u043e\u0434\u0430\u0436" in h
    )

    # Example:
    # "??? ????? ?????? ???????? ?????? ? ?????? ??? ??????????"
    #
    # This is closing + diagnosis, but NOT automatically BU/NU/VAT.
    if (
        educational_definition
        and explicit_diagnostic_intent
        and has_closing_form
        and not explicit_accounting_contour
    ):
        result.discard("accounting")


    # ------------------------------------------------------------
    # FINAL MOVEMENTS NORMALIZER V1
    # ------------------------------------------------------------

    # ------------------------------------------------------------
    # A. Posted document but expected posting/movement is absent
    # ------------------------------------------------------------
    #
    # This is simultaneously:
    # - a diagnostic problem;
    # - a document-movement problem.

    posted_document_missing_effect = (
        "\u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442" in h
        and (
            "\u043f\u0440\u043e\u0432\u0435\u0434\u0451\u043d" in h
            or "\u043f\u0440\u043e\u0432\u0435\u0434\u0435\u043d" in h
            or "\u043f\u0440\u043e\u0432\u0435\u0434\u0451\u043d\u043d" in h
            or "\u043f\u0440\u043e\u0432\u0435\u0434\u0435\u043d\u043d" in h
        )
        and (
            "\u043f\u0440\u043e\u0432\u043e\u0434\u043a" in h
            or "\u0434\u0432\u0438\u0436\u0435\u043d" in h
            or "\u0440\u0435\u0433\u0438\u0441\u0442\u0440" in h
        )
        and (
            "\u043d\u0435\u0442" in h
            or "\u043d\u0435 \u0441\u0444\u043e\u0440\u043c\u0438\u0440" in h
            or "\u043d\u0435 \u0441\u043e\u0437\u0434\u0430" in h
            or "\u043d\u0435 \u0434\u0435\u043b\u0430" in h
        )
    )

    if posted_document_missing_effect:
        result.add("movements")
        result.add("diagnosis")

    # ------------------------------------------------------------
    # B. Pure registrar/source tracing
    # ------------------------------------------------------------
    #
    # "There is a record in the report. How do I identify its
    # registrar?" is a tracing task, not yet a failure diagnosis.

    registrar_trace_question = (
        "\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440" in h
        and (
            "\u043a\u0430\u043a\u043e\u0439 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442" in h
            or "\u043a\u0430\u043a \u043f\u043e\u043d\u044f\u0442\u044c" in h
            or "\u043a\u0430\u043a \u043d\u0430\u0439\u0442\u0438" in h
            or "\u043e\u0442\u043a\u0443\u0434\u0430 \u0432\u0437\u044f\u043b\u0430\u0441\u044c" in h
            or "\u043e\u0442\u043a\u0443\u0434\u0430 \u043f\u043e\u044f\u0432\u0438\u043b\u0430\u0441\u044c" in h
        )
    )

    registrar_trace_failure = (
        "\u043e\u0448\u0438\u0431" in h
        or "\u043d\u0435 \u0441\u0445\u043e\u0434" in h
        or "\u0440\u0430\u0441\u0445\u043e\u0436\u0434" in h
        or "\u043d\u0435\u0432\u0435\u0440\u043d" in h
        or "\u043d\u0435 \u0440\u0430\u0431\u043e\u0442" in h
        or "\u043d\u0435\u0442 \u043f\u0440\u043e\u0432\u043e\u0434" in h
        or "\u043d\u0435\u0442 \u0434\u0432\u0438\u0436" in h
        or "\u043f\u043e\u0447\u0435\u043c\u0443" in h
    )

    if registrar_trace_question:
        result.add("movements")

        if not registrar_trace_failure:
            result.discard("diagnosis")


    # ------------------------------------------------------------
    # FINAL REPORTING NORMALIZER V1
    # ------------------------------------------------------------

    report_terms = (
        "\u043e\u0442\u0447\u0451\u0442",
        "\u043e\u0442\u0447\u0435\u0442",
        "\u043e\u0441\u0432",
        "\u0432\u0435\u0434\u043e\u043c\u043e\u0441\u0442",
        "\u043a\u043d\u0438\u0433\u0430 \u043f\u043e\u043a\u0443\u043f\u043e\u043a",
        "\u043a\u043d\u0438\u0433\u0435 \u043f\u043e\u043a\u0443\u043f\u043e\u043a",
        "\u043a\u043d\u0438\u0433\u0443 \u043f\u043e\u043a\u0443\u043f\u043e\u043a",
        "\u043a\u043d\u0438\u0433\u043e\u0439 \u043f\u043e\u043a\u0443\u043f\u043e\u043a",
        "\u043a\u043d\u0438\u0433\u0430 \u043f\u0440\u043e\u0434\u0430\u0436",
        "\u043a\u043d\u0438\u0433\u0435 \u043f\u0440\u043e\u0434\u0430\u0436",
        "\u043a\u043d\u0438\u0433\u0443 \u043f\u0440\u043e\u0434\u0430\u0436",
        "\u043a\u043d\u0438\u0433\u043e\u0439 \u043f\u0440\u043e\u0434\u0430\u0436",
    )

    report_investigation_intent = (
        "\u043e\u0442\u043a\u0443\u0434\u0430" in h
        or "\u043f\u043e\u0447\u0435\u043c\u0443" in h
        or "\u0440\u0430\u0441\u0448\u0438\u0444\u0440" in h
        or "\u043d\u0435 \u0441\u0445\u043e\u0434" in h
        or "\u0440\u0430\u0441\u0445\u043e\u0436\u0434" in h
        or "\u043d\u0435 \u0441\u043e\u0432\u043f\u0430\u0434" in h
        or "\u0440\u0430\u0437\u043d\u0438\u0446" in h

        # A report value / line / total changed.
        # This is intentionally scoped by `has_report_term` below,
        # so generic phrases such as "document changed" do not by
        # themselves activate report analysis.
        or "\u0438\u0437\u043c\u0435\u043d" in h

        or "\u043a\u0430\u043a\u043e\u0439 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442" in h
        or "\u043a\u0430\u043a\u0438\u043c \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u043e\u043c" in h
        or "\u0447\u0442\u043e \u0441\u0444\u043e\u0440\u043c\u0438\u0440\u043e\u0432\u0430\u043b" in h
        or "\u0447\u0435\u043c \u0441\u0444\u043e\u0440\u043c\u0438\u0440\u043e\u0432\u0430\u043d" in h
        or "\u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a \u0441\u0442\u0440\u043e\u043a" in h
        or "\u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a \u0441\u0443\u043c\u043c" in h
    )

    has_report_term = any(
        marker in h
        for marker in report_terms
    )

    pure_report_definition = (
        h.strip().startswith(
            "\u0447\u0442\u043e \u0442\u0430\u043a\u043e\u0435 \u043e\u0441\u0432"
        )
        or h.strip().startswith(
            "\u0447\u0442\u043e \u0442\u0430\u043a\u043e\u0435 \u043e\u0442\u0447\u0451\u0442"
        )
        or h.strip().startswith(
            "\u0447\u0442\u043e \u0442\u0430\u043a\u043e\u0435 \u043e\u0442\u0447\u0435\u0442"
        )
    )

    if (
        has_report_term
        and report_investigation_intent
        and not pure_report_definition
    ):
        result.add("reporting")

    # If the user explicitly asks which document formed a report
    # row/value, this is both report analysis and source tracing.
    report_to_document_trace = (
        has_report_term
        and (
            "\u043a\u0430\u043a\u043e\u0439 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442" in h
            or "\u043a\u0430\u043a\u0438\u043c \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u043e\u043c" in h
            or "\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440" in h
        )
    )

    if report_to_document_trace:
        result.add("reporting")
        result.add("movements")

    return frozenset(result)


def select_skills(text: str, *, limit: int = 3) -> tuple[Skill, ...]:
    """
    Select skills using semantic task priority first and literal
    trigger strength only as a tie-breaker.

    The goal is composition, not keyword competition.

    Example:
        reporting + accounting + closing + diagnosis

    with limit=3 should keep:
        reporting + accounting + closing

    and drop generic diagnosis.
    """

    haystack = (text or "").casefold()

    if not haystack.strip() or limit <= 0:
        return ()

    task_types = infer_task_types(haystack)

    if not task_types:
        return ()

    # Higher value = more important to preserve when more task types
    # are relevant than the skill limit allows.
    #
    # "diagnosis" is intentionally generic and therefore has the
    # lowest priority. It remains active when there is free capacity
    # or when diagnosis is the main/only task.
    task_priority = {
        "meeting": 100,
        "reporting": 95,
        "movements": 90,
        "accounting": 88,
        "reconciliation": 86,
        "closing": 84,
        "testing": 82,
        "requirements": 80,
        "diagnosis": 60,
    }

    candidates = []

    for skill in load_skills():
        trigger_score = 0

        for trigger in skill.triggers:
            if _trigger_matches(haystack, trigger):
                trigger_score += max(1, len(trigger))

        # --------------------------------------------------------
        # Typed skills
        # --------------------------------------------------------

        if skill.task_types:
            overlap = set(skill.task_types).intersection(task_types)

            if not overlap:
                continue

            # Semantic classification is authoritative.
            # A literal trigger is not required once the task type
            # has already been established.
            best_priority = max(
                task_priority.get(task_type, 40)
                for task_type in overlap
            )

            overlap_count = len(overlap)

            candidates.append(
                (
                    best_priority,
                    overlap_count,
                    trigger_score,
                    skill.skill_id,
                    skill,
                )
            )

        # --------------------------------------------------------
        # Legacy / untyped skills
        # --------------------------------------------------------

        else:
            if trigger_score <= 0:
                continue

            candidates.append(
                (
                    30,
                    0,
                    trigger_score,
                    skill.skill_id,
                    skill,
                )
            )

    # Priority:
    #
    # 1. semantic task importance;
    # 2. number of relevant task types;
    # 3. literal trigger evidence;
    # 4. stable skill id for deterministic ordering.
    candidates.sort(
        key=lambda item: (
            -item[0],
            -item[1],
            -item[2],
            item[3],
        )
    )

    return tuple(
        item[4]
        for item in candidates[:limit]
    )


def build_skill_context(text: str) -> str:
    selected = select_skills(text)

    if not selected:
        return ""

    parts = [
        "ACTIVE ANALYST SKILLS:",
        (
            "Apply the following procedural skills to the CURRENT request. "
            "They are working methods, not additional facts about the case. "
            "Never invent source data merely because a skill mentions a check."
        ),
    ]

    for skill in selected:
        parts.append(
            "\n"
            f"===== SKILL: {skill.skill_id} / {skill.name} =====\n"
            f"{skill.body}\n"
            f"===== END SKILL: {skill.skill_id} ====="
        )

    return "\n".join(parts).strip()
