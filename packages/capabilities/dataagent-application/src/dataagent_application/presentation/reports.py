"""Report composition and export (DA10.3.1 / DA10.3.3, 07 §5.5).

``compose_document_report`` builds a structured ``ReportDraft`` (conclusion,
per-section evidence, undecidable items, not-covered scope, optional
acceptance summary) and stores it as a versioned object.
``export_report_format`` renders md / html (stdlib) or docx (optional
dependency group) and stores the artifact content-addressed. Export is not
publication.
"""

from __future__ import annotations

import html as html_module
from typing import Any

from pydantic import BaseModel, ConfigDict, Field as PydanticField

from dataagent_contracts.core import (
    AssetRef,
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    EvidenceRef,
    Issue,
    Severity,
    VersionedRef,
)

from dataagent_application import helpers
from dataagent_application.contracts import ReportDraft, ReportSection
from dataagent_runtime.errors import invalid_input
from dataagent_runtime.registry import operation


class _IO(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- DA10.3.1 ----------------------------------------------------------------


class ComposeDocumentReportInput(_IO):
    title: str = PydanticField(min_length=1)
    conclusion: str = PydanticField(min_length=1)
    sections: list[dict[str, Any]] = PydanticField(default_factory=list)
    evidence: list[dict[str, Any]] = PydanticField(default_factory=list)
    undecidable: list[str] = PydanticField(default_factory=list)
    not_covered: list[str] = PydanticField(default_factory=list)
    acceptance_summary: str | None = None


class ComposeDocumentReportOutput(_IO):
    draft: ReportDraft
    report_ref: VersionedRef
    markdown: str


def _render_markdown(draft: ReportDraft) -> str:
    lines = [f"# {draft.title}", "", draft.conclusion, ""]
    for section in draft.sections:
        lines += [f"## {section.heading}", "", section.body_markdown, ""]
        if section.evidence_refs:
            lines += ["依据: " + ", ".join(section.evidence_refs), ""]
    if draft.evidence:
        lines += ["## 依据", ""]
        for item in draft.evidence:
            anchors = (
                " (anchors: "
                + ", ".join(
                    f"{a.source_ref}@{a.source_revision}" for a in item.source_anchors
                )
                + ")"
                if item.source_anchors
                else ""
            )
            lines.append(f"- `{item.id}` [{item.evidence_type}]{anchors}")
        lines.append("")
    if draft.undecidable:
        lines += ["## 不可判定项", ""] + [f"- {item}" for item in draft.undecidable] + [""]
    if draft.not_covered:
        lines += ["## 未覆盖范围", ""] + [f"- {item}" for item in draft.not_covered] + [""]
    if draft.acceptance_summary:
        lines += ["## 验收结论", "", draft.acceptance_summary, ""]
    return "\n".join(lines).rstrip() + "\n"


@operation(
    "DA10.3.1",
    input_model=ComposeDocumentReportInput,
    output_model=ComposeDocumentReportOutput,
    description="文档报告生成：结论、逐条依据（EvidenceRef→原文锚点）、不可判定项与未覆盖范围、验收摘要（DA10.3.1）",
    writes=True,
)
def compose_document_report(
    data: ComposeDocumentReportInput, ctx: CallContext, runtime
) -> CapabilityResult[ComposeDocumentReportOutput]:
    sections = [ReportSection.model_validate(item) for item in data.sections]
    evidence = [EvidenceRef.model_validate(item) for item in data.evidence]
    evidence_ids = {item.id for item in evidence}
    unresolvable = sorted(
        {ref for section in sections for ref in section.evidence_refs} - evidence_ids
    )
    if unresolvable:
        raise invalid_input(
            f"section evidence_refs that no EvidenceRef backs: {unresolvable}",
            target="sections.evidence_refs",
        )
    markdown_payload = _markdown_for(
        data.title, data.conclusion, sections, evidence,
        data.undecidable, data.not_covered, data.acceptance_summary,
    )
    digest = runtime.content.put(markdown_payload)
    draft = ReportDraft(
        draft_id=f"report:{digest.split(':', 1)[1][:16]}",
        revision="r1",
        title=data.title,
        conclusion=data.conclusion,
        sections=sections,
        evidence=evidence,
        undecidable=data.undecidable,
        not_covered=data.not_covered,
        acceptance_summary=data.acceptance_summary,
    )
    payload = draft.model_dump(mode="json")
    revision = runtime.versions.save("report_draft", draft.draft_id, payload)
    report_ref = VersionedRef(id=draft.draft_id, revision=revision)
    return CapabilityResult[ComposeDocumentReportOutput](
        status=CapabilityStatus.ok,
        data=ComposeDocumentReportOutput(
            draft=draft, report_ref=report_ref, markdown=markdown_payload
        ),
        completeness=helpers.complete(
            "report composition",
            {"sections": len(sections), "evidence": len(evidence)},
        ),
    )


def _markdown_for(
    title: str,
    conclusion: str,
    sections: list[ReportSection],
    evidence: list[EvidenceRef],
    undecidable: list[str],
    not_covered: list[str],
    acceptance_summary: str | None,
) -> str:
    return _render_markdown(
        ReportDraft(
            draft_id="draft",
            revision="r0",
            title=title,
            conclusion=conclusion,
            sections=sections,
            evidence=evidence,
            undecidable=undecidable,
            not_covered=not_covered,
            acceptance_summary=acceptance_summary,
        )
    )


# --- DA10.3.3 ----------------------------------------------------------------


class ExportReportFormatInput(_IO):
    report_ref: VersionedRef | None = None
    draft: dict[str, Any] | None = None
    format: str = PydanticField(pattern="^(md|html|docx)$")


class ExportReportFormatOutput(_IO):
    asset: AssetRef
    format: str


def _render_html(draft: ReportDraft, markdown: str) -> str:
    def esc(text: str) -> str:
        return html_module.escape(text)

    parts = [f"<h1>{esc(draft.title)}</h1>", f"<p>{esc(draft.conclusion)}</p>"]
    for section in draft.sections:
        parts.append(f"<h2>{esc(section.heading)}</h2>")
        parts.append(f"<p>{esc(section.body_markdown)}</p>")
        if section.evidence_refs:
            parts.append(
                "<ul>"
                + "".join(f"<li>{esc(ref)}</li>" for ref in section.evidence_refs)
                + "</ul>"
            )
    if draft.undecidable:
        parts.append("<h2>不可判定项</h2><ul>")
        parts.extend(f"<li>{esc(item)}</li>" for item in draft.undecidable)
        parts.append("</ul>")
    if draft.not_covered:
        parts.append("<h2>未覆盖范围</h2><ul>")
        parts.extend(f"<li>{esc(item)}</li>" for item in draft.not_covered)
        parts.append("</ul>")
    if draft.acceptance_summary:
        parts.append(f"<h2>验收结论</h2><p>{esc(draft.acceptance_summary)}</p>")
    return "\n".join(parts) + "\n"


def _render_docx(draft: ReportDraft, markdown: str) -> bytes:
    try:
        import docx  # python-docx (optional dependency group)
    except ImportError as exc:
        from dataagent_runtime.errors import dependency_unavailable

        raise dependency_unavailable(
            "docx export needs the optional dependency python-docx",
            action="install the 'docx' extra or export md/html instead",
        ) from exc

    document = docx.Document()
    document.add_heading(draft.title, level=0)
    document.add_paragraph(draft.conclusion)
    for section in draft.sections:
        document.add_heading(section.heading, level=1)
        document.add_paragraph(section.body_markdown)
        for ref in section.evidence_refs:
            document.add_paragraph(f"依据: {ref}", style="List Bullet")
    if draft.undecidable:
        document.add_heading("不可判定项", level=1)
        for item in draft.undecidable:
            document.add_paragraph(item, style="List Bullet")
    if draft.not_covered:
        document.add_heading("未覆盖范围", level=1)
        for item in draft.not_covered:
            document.add_paragraph(item, style="List Bullet")
    if draft.acceptance_summary:
        document.add_heading("验收结论", level=1)
        document.add_paragraph(draft.acceptance_summary)
    import io

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


_MEDIA_TYPES = {
    "md": "text/markdown",
    "html": "text/html",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@operation(
    "DA10.3.3",
    input_model=ExportReportFormatInput,
    output_model=ExportReportFormatOutput,
    description="报告格式导出：md/html（标准库）、docx（可选依赖组）；内容寻址保存返回 AssetRef；导出不等于发布（DA10.3.3）",
    writes=True,
)
def export_report_format(
    data: ExportReportFormatInput, ctx: CallContext, runtime
) -> CapabilityResult[ExportReportFormatOutput]:
    if data.draft is not None:
        draft = ReportDraft.model_validate(data.draft)
    elif data.report_ref is not None:
        ref = data.report_ref
        payload = runtime.versions.get("report_draft", ref.id, ref.revision)
        if payload is None:
            raise invalid_input(f"report draft not found: {ref}", target="report_ref")
        draft = ReportDraft.model_validate(payload)
    else:
        raise invalid_input("provide a draft inline or a report_ref", target="report_ref")

    markdown = _render_markdown(draft)
    if data.format == "md":
        content = markdown.encode("utf-8")
    elif data.format == "html":
        content = _render_html(draft, markdown).encode("utf-8")
    else:
        content = _render_docx(draft, markdown)

    digest = runtime.content.put(content)
    asset = helpers.asset_for(
        digest,
        "report_export",
        ctx.scope_ref,
        media_type=_MEDIA_TYPES[data.format],
    )
    issues = [
        Issue(
            code="da10.export_not_publication",
            severity=Severity.info,
            message="export produces a stored artifact; publication is a separate decision",
            retryable=False,
        )
    ]
    return CapabilityResult[ExportReportFormatOutput](
        status=CapabilityStatus.ok,
        data=ExportReportFormatOutput(asset=asset, format=data.format),
        issues=issues,
        completeness=helpers.complete("report export"),
    )
