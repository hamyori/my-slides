"""Build the static catalog for the presentations in ``slides/``."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from datetime import date
from html import escape as escape_html
from html.parser import HTMLParser
from math import ceil
from pathlib import Path
from textwrap import wrap
from typing import Any


METADATA_FIELDS = {
    "title",
    "date",
    "course",
    "tags",
    "description",
    "author",
    "duration_minutes",
    "preview",
}
REQUIRED_FIELDS = ("title", "date", "course", "description")
SKIP_TEXT_TAGS = {"script", "style", "noscript", "svg"}


class SlideParser(HTMLParser):
    """Extract catalog fields and readable text without executing deck scripts."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {field: "" for field in METADATA_FIELDS}
        self.title_parts: list[str] = []
        self.full_text_parts: list[str] = []
        self.slide_titles: list[str] = []
        self.slide_count = 0
        self.slide_section_stack: list[bool] = []
        self.body_depth = 0
        self.slide_depth = 0
        self.skipped_depth = 0
        self.in_document_title = False
        self.in_slide_heading = False
        self.heading_parts: list[str] = []
        self.heading_seen_for_slide = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {key.lower(): value or "" for key, value in attrs}

        if tag == "meta":
            name = attr_dict.get("name", "").strip().lower().replace("-", "_")
            if name in METADATA_FIELDS:
                self.meta[name] = attr_dict.get("content", "").strip()

        if tag == "title":
            self.in_document_title = True
        if tag == "body":
            self.body_depth += 1
        if tag in SKIP_TEXT_TAGS:
            self.skipped_depth += 1

        if tag == "section":
            classes = set(attr_dict.get("class", "").split())
            is_slide = "slide" in classes
            self.slide_section_stack.append(is_slide)
            if is_slide:
                if self.slide_depth == 0:
                    self.heading_seen_for_slide = False
                    self.slide_count += 1
                self.slide_depth += 1

        if tag in {"h1", "h2", "h3"} and self.slide_depth and not self.heading_seen_for_slide:
            self.in_slide_heading = True
            self.heading_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_document_title = False
        if tag in {"h1", "h2", "h3"} and self.in_slide_heading:
            heading = " ".join(" ".join(self.heading_parts).split())
            if heading:
                self.slide_titles.append(heading)
                self.heading_seen_for_slide = True
            self.in_slide_heading = False
        if tag == "section" and self.slide_section_stack:
            if self.slide_section_stack.pop():
                self.slide_depth = max(0, self.slide_depth - 1)
        if tag in SKIP_TEXT_TAGS or tag == "body":
            if tag == "body":
                self.body_depth = max(0, self.body_depth - 1)
            elif self.skipped_depth:
                self.skipped_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.in_document_title:
            self.title_parts.append(data)
        if self.in_slide_heading:
            self.heading_parts.append(data)
        if self.body_depth and not self.skipped_depth:
            text = " ".join(data.split())
            if text:
                self.full_text_parts.append(text)


def normalize_date(value: str, folder_name: str) -> str:
    """Return an ISO date, using a YYYY-M-D folder prefix as a fallback."""
    candidate = value.strip()
    if not candidate:
        match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:-|$)", folder_name)
        if match:
            year, month, day = (int(part) for part in match.groups())
            candidate = f"{year:04d}-{month:02d}-{day:02d}"
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
        return ""
    try:
        return date.fromisoformat(candidate).isoformat()
    except ValueError:
        return ""


def parse_presentation(html_file: Path, root_dir: Path) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    try:
        content = html_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return None, [f"{html_file}: cannot read file ({error})"]

    parser = SlideParser()
    try:
        parser.feed(content)
        parser.close()
    except Exception as error:  # HTMLParser errors should not hide which deck failed.
        return None, [f"{html_file}: invalid HTML ({error})"]

    title = parser.meta["title"] or " ".join(" ".join(parser.title_parts).split())
    parsed_date = normalize_date(parser.meta["date"], html_file.parent.name)
    metadata = {
        "title": title,
        "date": parsed_date,
        "course": parser.meta["course"].strip(),
        "tags": [tag.strip() for tag in parser.meta["tags"].split(",") if tag.strip()],
        "description": parser.meta["description"].strip(),
        "author": parser.meta["author"].strip(),
        "duration_minutes": None,
        "duration_estimated": True,
        "preview": "",
        "slide_count": parser.slide_count,
        "slide_titles": parser.slide_titles,
        "full_text": " ".join(parser.full_text_parts).lower()[:10000],
        "url": html_file.relative_to(root_dir).as_posix(),
    }

    raw_duration = parser.meta["duration_minutes"].strip()
    if raw_duration:
        try:
            duration = int(raw_duration)
            if duration < 1:
                raise ValueError
            metadata["duration_minutes"] = duration
            metadata["duration_estimated"] = False
        except ValueError:
            errors.append(f"{html_file}: duration_minutes must be a positive integer")
    elif parser.slide_count:
        metadata["duration_minutes"] = max(1, ceil(parser.slide_count * 1.2))

    raw_preview = parser.meta["preview"].strip()
    if raw_preview:
        preview_path = (html_file.parent / raw_preview).resolve()
        try:
            preview_path.relative_to(root_dir.resolve())
        except ValueError:
            errors.append(f"{html_file}: preview must point to a file inside the repository")
        else:
            if not preview_path.is_file():
                errors.append(f"{html_file}: preview file does not exist: {raw_preview}")
            else:
                metadata["preview"] = preview_path.relative_to(root_dir.resolve()).as_posix()

    for field in REQUIRED_FIELDS:
        value = metadata[field]
        if not value:
            errors.append(f"{html_file}: missing required metadata: {field}")
    if parser.slide_count == 0:
        errors.append(f'{html_file}: no <section class="slide"> sections found')
    if metadata["date"] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", metadata["date"]):
        errors.append(f"{html_file}: date must use YYYY-MM-DD")

    if errors:
        return None, errors
    return metadata, []


def generate_cover_preview(title: str, course: str) -> str:
    """Create a dependency-free, branded SVG cover when a deck has no image."""
    title_lines = wrap(title, width=25, max_lines=3, placeholder="…") or [title]
    title_markup = "".join(
        f'<text x="72" y="{300 + index * 76}" fill="#ffffff" font-family="Arial,sans-serif" font-size="58" font-weight="700">{escape_html(line)}</text>'
        for index, line in enumerate(title_lines)
    )
    safe_course = escape_html(course.upper())
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675" role="img" aria-label="{escape_html(title)}">
  <defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#101827"/><stop offset="1" stop-color="#304765"/></linearGradient></defs>
  <rect width="1200" height="675" fill="url(#bg)"/>
  <path d="M910 0h290v675H750z" fill="#e85d5d" opacity=".9"/>
  <path d="M0 36h1200" stroke="#e85d5d" stroke-width="12"/>
  <text x="72" y="115" fill="#a9cfff" font-family="Arial,sans-serif" font-size="24" font-weight="700" letter-spacing="4">{safe_course}</text>
  {title_markup}
  <text x="74" y="596" fill="#d7e0ea" font-family="Arial,sans-serif" font-size="21" letter-spacing="3">PRESENTACIÓN ACADÉMICA</text>
</svg>\n'''


def build_index(
    slides_dir: str | Path = "slides",
    output_file: str | Path = "presentaciones.json",
    root_dir: str | Path = ".",
) -> list[dict[str, Any]]:
    root = Path(root_dir).resolve()
    slides_path = Path(slides_dir)
    if not slides_path.is_absolute():
        slides_path = root / slides_path
    output_path = Path(output_file)
    if not output_path.is_absolute():
        output_path = root / output_path

    html_files = sorted(slides_path.rglob("*.html")) if slides_path.exists() else []
    errors: list[str] = []
    presentations: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    if not html_files:
        errors.append(f"{slides_path}: no presentation HTML files found")

    for html_file in html_files:
        try:
            html_file.relative_to(root)
        except ValueError:
            errors.append(f"{html_file}: presentation must be inside the repository root")
            continue

        presentation, parse_errors = parse_presentation(html_file, root)
        errors.extend(parse_errors)
        if presentation is None:
            continue
        if presentation["url"] in seen_urls:
            errors.append(f"{html_file}: duplicate URL {presentation['url']}")
            continue
        seen_urls.add(presentation["url"])
        presentations.append(presentation)

    if errors:
        raise ValueError("\n".join(errors))

    for presentation in presentations:
        if presentation["preview"]:
            continue
        preview_path = root / Path(presentation["url"]).parent / "catalog-preview.generated.svg"
        preview_path.write_text(
            generate_cover_preview(presentation["title"], presentation["course"]),
            encoding="utf-8",
        )
        presentation["preview"] = preview_path.relative_to(root).as_posix()

    presentations.sort(key=lambda item: (item["date"], item["title"].casefold()), reverse=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output_path.parent, delete=False) as temporary:
        json.dump(presentations, temporary, ensure_ascii=False, indent=2)
        temporary.write("\n")
        temporary_path = Path(temporary.name)
    temporary_path.replace(output_path)
    return presentations


def main() -> int:
    argument_parser = argparse.ArgumentParser(description=__doc__)
    argument_parser.add_argument("--slides", default="slides", help="directory to scan (default: slides)")
    argument_parser.add_argument("--output", default="presentaciones.json", help="index output path")
    argument_parser.add_argument("--root", default=".", help="repository root for generated relative URLs")
    args = argument_parser.parse_args()

    try:
        presentations = build_index(args.slides, args.output, args.root)
    except (OSError, ValueError) as error:
        print(f"Index generation failed:\n{error}", file=sys.stderr)
        return 1

    print(f"Indexed {len(presentations)} presentation(s) into {args.output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
