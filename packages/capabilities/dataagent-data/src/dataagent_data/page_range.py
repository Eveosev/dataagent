"""Page range parsing ("1-3,5")."""

from __future__ import annotations

from dataagent_runtime.errors import invalid_input


def parse_page_range(spec: str, page_count: int) -> list[int]:
    pages: list[int] = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            try:
                start, end = int(start_text), int(end_text)
            except ValueError as exc:
                raise invalid_input(f"invalid page range: {token}") from exc
            if start < 1 or end < start or end > page_count:
                raise invalid_input(f"page range out of bounds: {token} (pages={page_count})")
            pages.extend(range(start, end + 1))
        else:
            try:
                page = int(token)
            except ValueError as exc:
                raise invalid_input(f"invalid page: {token}") from exc
            if page < 1 or page > page_count:
                raise invalid_input(f"page out of bounds: {page} (pages={page_count})")
            pages.append(page)
    if not pages:
        raise invalid_input("page range selects no pages")
    return sorted(dict.fromkeys(pages))
