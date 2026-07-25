"""Task Document v1 parser/compiler.

A Task Document is a UTF-8 Markdown file with an optional YAML front
matter delimited by ``---`` (same convention as skill ``SKILL.md``
front matter). This module:

* splits the document into a ``Document`` (front-matter metadata + named
  Markdown sections + raw body for the ``full`` view),
* validates required sections and the Chinese enum literals,
* compiles the parsed structure into the API body used by the legacy
  ``create_task`` / ``update_task`` paths (still used by the deprecated
  v2 tools).

Only the parser/compiler live here. The MCP tools that consume this
module land in later commits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from .models import TaskKind, TaskPriority, TaskType

FRONT_MATTER_DELIM = "---"

# Canonical section names are case-folded. The keys here are the canonical
# (lowercase, stripped) form; values are the matching alternative names.
CANONICAL_SECTIONS: dict[str, tuple[str, ...]] = {
    "goal": ("goal",),
    "plan": ("plan",),
    "acceptance criteria": ("acceptance criteria", "acceptance_criteria", "ac"),
    "constraints": ("constraints",),
    "context pointers": ("context pointers", "context_pointers"),
    "decisions": ("decisions",),
    "out of scope": ("out of scope", "out_of_scope"),
}

REQUIRED_SECTIONS: tuple[str, ...] = ("goal", "acceptance criteria")

SECTION_ORDER: tuple[str, ...] = (
    "goal",
    "plan",
    "acceptance criteria",
    "constraints",
    "context pointers",
    "decisions",
    "out of scope",
)


class DocumentError(ValueError):
    """Raised for any structural problem in a Task Document."""


@dataclass
class DocumentSection:
    canonical: str
    body: str


@dataclass
class TaskDocument:
    metadata: dict[str, Any]
    sections: dict[str, str] = field(default_factory=dict)
    extra_sections: list[DocumentSection] = field(default_factory=list)
    raw_markdown: str = ""

    def section(self, name: str) -> Optional[str]:
        return self.sections.get(_normalise_section(name))

    def to_body(self) -> dict[str, Any]:
        """Compile the document into an API body (structured + detail)."""
        body: dict[str, Any] = {
            "title": self.metadata["title"],
            "type": self.metadata["task_type"],
            "priority": self.metadata["priority"],
            "scope": self.metadata["scope"],
        }
        if "kind" in self.metadata:
            body["kind"] = self.metadata["kind"]
        if "for_agent" in self.metadata:
            body["for_agent"] = bool(self.metadata["for_agent"])
        if "due_date" in self.metadata:
            body["due_date"] = self.metadata["due_date"]
        if "blocked_by" in self.metadata:
            body["blocked_by"] = list(self.metadata["blocked_by"])
        if "parent_slug" in self.metadata:
            body["parent_slug"] = self.metadata["parent_slug"]

        detail = self._render_markdown()
        if detail:
            body["detail"] = detail
        return body

    def _render_markdown(self) -> str:
        """Render canonical sections plus extras into a single Markdown body."""
        out: list[str] = []
        ordered_canonicals = [c for c in SECTION_ORDER if c in self.sections]
        # Anything not in SECTION_ORDER (extras) keeps its original order at
        # the end so nothing is silently dropped from ``full`` views.
        extras = {e.canonical for e in self.extra_sections}
        for canonical in ordered_canonicals:
            out.append(f"## {canonical.title()}")
            out.append(self.sections[canonical].rstrip())
        for extra in self.extra_sections:
            if extra.canonical in self.sections or extra.canonical in extras:
                continue
            out.append(f"## {extra.canonical.title()}")
            out.append(extra.body.rstrip())
        return "\n\n".join(s for s in out if s).strip() + "\n"


# --- front matter -----------------------------------------------------------


def _split_front_matter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith(f"{FRONT_MATTER_DELIM}\n"):
        return {}, raw
    lines = raw.splitlines(keepends=False)
    if not lines or lines[0].strip() != FRONT_MATTER_DELIM:
        return {}, raw
    closing_idx: Optional[int] = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == FRONT_MATTER_DELIM:
            closing_idx = idx
            break
    if closing_idx is None:
        raise DocumentError("front matter 以 --- 开始但没有匹配的结束分隔符")
    front_text = "\n".join(lines[1:closing_idx])
    body = "\n".join(lines[closing_idx + 1 :])
    try:
        metadata = yaml.safe_load(front_text)
    except yaml.YAMLError as exc:
        raise DocumentError(f"front matter 解析失败: {exc}") from exc
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise DocumentError("front matter 必须是 YAML 映射（key: value）")
    return metadata, body


# --- section parsing --------------------------------------------------------


_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*$")


def _normalise_section(title: str) -> str:
    return title.strip().lower()


def _section_canonical(title: str) -> str:
    normalised = _normalise_section(title)
    for canonical, aliases in CANONICAL_SECTIONS.items():
        if normalised in aliases:
            return canonical
    return normalised


def _parse_sections(body: str) -> tuple[dict[str, str], list[DocumentSection], list[str]]:
    """Return (canonical_sections, extras_in_order, unknown_titles)."""
    canonical: dict[str, str] = {}
    extras: list[DocumentSection] = []
    unknown: list[str] = []

    current_title: Optional[str] = None
    current_canonical: Optional[str] = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_canonical, current_lines
        if current_title is None:
            return
        text = "\n".join(current_lines).strip("\n")
        canonical_name = _section_canonical(current_title)
        if canonical_name in CANONICAL_SECTIONS:
            if canonical_name in canonical:
                raise DocumentError(f"section 重复: {current_title}")
            canonical[canonical_name] = text
        else:
            extras.append(DocumentSection(canonical=canonical_name, body=text))
            unknown.append(current_title)
        current_title = None
        current_canonical = None
        current_lines = []

    for line in body.splitlines():
        match = _HEADING_RE.match(line)
        if match and len(match.group("hashes")) == 2:
            flush()
            current_title = match.group("title")
            current_lines = []
        else:
            if current_title is not None:
                current_lines.append(line)
    flush()
    return canonical, extras, unknown


# --- validation -------------------------------------------------------------


def _validate_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []

    title = metadata.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append("title 必填且必须是非空字符串")
    metadata["title"] = title.strip() if isinstance(title, str) else title

    task_type = metadata.get("task_type")
    if task_type not in TaskType.__args__:
        errors.append(
            f"task_type 必须是 {TaskType.__args__} 之一，实际: {task_type!r}"
        )

    priority = metadata.get("priority")
    if priority not in TaskPriority.__args__:
        errors.append(
            f"priority 必须是 {TaskPriority.__args__} 之一，实际: {priority!r}"
        )

    scope = metadata.get("scope")
    if not isinstance(scope, str) or not scope.strip():
        errors.append("scope 必填且必须是非空字符串")
    else:
        metadata["scope"] = scope.strip()

    kind = metadata.get("kind")
    if kind is not None and kind not in TaskKind.__args__:
        errors.append(f"kind 必须是 {TaskKind.__args__} 之一，实际: {kind!r}")

    if "for_agent" in metadata and not isinstance(metadata["for_agent"], bool):
        errors.append("for_agent 必须是 bool")

    if "blocked_by" in metadata:
        bb = metadata["blocked_by"]
        if not isinstance(bb, list) or not all(isinstance(x, str) for x in bb):
            errors.append("blocked_by 必须是字符串列表")

    if "due_date" in metadata and not isinstance(metadata["due_date"], str):
        errors.append("due_date 必须是 ISO-8601 字符串")

    if "parent_slug" in metadata and not isinstance(metadata["parent_slug"], str):
        errors.append("parent_slug 必须是字符串")

    if errors:
        raise DocumentError("; ".join(errors))
    return metadata


def _validate_sections(sections: dict[str, str]) -> None:
    missing = [s for s in REQUIRED_SECTIONS if not sections.get(s)]
    if missing:
        labels = [s.title() for s in missing]
        raise DocumentError(f"必填 section 缺失: {', '.join(labels)}")
    ac = sections["acceptance criteria"]
    if not any(line.lstrip().startswith("- [ ]") for line in ac.splitlines()):
        raise DocumentError(
            "Acceptance Criteria 必须至少包含一条 `- [ ]` 形式的检查项"
        )


# --- entry point ------------------------------------------------------------


def parse_task_document(text: str) -> TaskDocument:
    """Parse a single Task Document and validate it.

    Args:
        text: Full file contents as UTF-8 text.

    Returns:
        A :class:`TaskDocument` ready to be turned into an API body.
    """
    if not isinstance(text, str):
        raise DocumentError("Task Document 必须是字符串")
    metadata, body = _split_front_matter(text)
    if not metadata:
        raise DocumentError(
            "Task Document 必须以 YAML front matter 开头（--- 包裹）"
        )
    metadata = _validate_metadata(metadata)
    sections, extras, _unknown = _parse_sections(body)
    _validate_sections(sections)
    return TaskDocument(
        metadata=metadata,
        sections=sections,
        extra_sections=extras,
        raw_markdown=body,
    )


def parse_task_document_file(path: str | Path) -> TaskDocument:
    """Convenience: read a path and call :func:`parse_task_document`."""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise DocumentError("Task Document 必须是 UTF-8 编码") from exc
    except OSError as exc:
        raise DocumentError(f"无法读取 Task Document: {exc}") from exc
    return parse_task_document(text)
