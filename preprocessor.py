"""
preprocessor.py — Document preprocessing.

Responsibilities:
- Clean and normalize raw text
- Extract structured metadata (professor name, rating, course codes)
- Inject metadata into RMP review chunks before chunking
- Parse and restructure Reddit threads into per-topic blocks for chunking
- Prepare documents for their respective chunking strategies
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from logger import get_session_logger

logger = get_session_logger()

# ---------------------------------------------------------------------------
# RateMyProfessor preprocessing
# ---------------------------------------------------------------------------

def extract_rmp_header(raw_text: str) -> dict:
    """
    Parse the structured header block at the top of an RMP .txt file.
    Returns a dict with: professor_name, overall_quality, difficulty, would_take_again, source_url.
    This is pure Python — the header format is consistent and machine-readable.
    """
    header = {}

    source_match = re.search(r"SOURCE:\s*(.+)", raw_text)
    header["source_url"] = source_match.group(1).strip() if source_match else ""

    name_match = re.search(r"PROFESSOR NAME:\s*(.+)", raw_text)
    header["professor_name"] = name_match.group(1).strip() if name_match else ""

    quality_match = re.search(r"Based on \d+ ratings?:\s*([\d.]+)\s*/\s*5", raw_text)
    header["overall_quality"] = float(quality_match.group(1)) if quality_match else None

    difficulty_match = re.search(r"LEVEL OF DIFFICULTY:\s*([\d.]+)", raw_text)
    header["difficulty"] = float(difficulty_match.group(1)) if difficulty_match else None

    again_match = re.search(r"WOULD TAKE AGAIN:\s*([\d.]+)%", raw_text)
    header["would_take_again_pct"] = float(again_match.group(1)) if again_match else None

    logger.debug(f"RMP header output: {header}")

    return header


def split_rmp_reviews(raw_text: str) -> list[str]:
    """
    Split an RMP document into individual review blocks.
    Reviews start after the 'STUDENT RATINGS:' header and are separated by blank lines.
    """
    # Find the start of the review section
    match = re.search(r"STUDENT RATINGS:\s*\n", raw_text)
    if not match:
        return []

    reviews_section = raw_text[match.end():]

    # Each review starts with a date pattern (e.g. "Jan 9th, 2026")
    date_pattern = re.compile(
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+\w*,\s+\d{4}"
    )
    positions = [m.start() for m in date_pattern.finditer(reviews_section)]

    if not positions:
        return []

    reviews = []
    for i, start in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(reviews_section)
        reviews.append(reviews_section[start:end].strip())

    logger.debug(f"RMP reviews: {reviews}")

    return reviews


def inject_metadata_into_review(review_text: str, header: dict) -> str:
    """
    Prepend professor context to a single review so the chunk is self-contained.
    This is critical because individual reviews never mention the professor by name.
    """
    meta_prefix = (
        f"Professor: {header.get('professor_name', 'Unknown')} | "
        f"Overall Quality: {header.get('overall_quality', 'N/A')}/5 | "
        f"Difficulty: {header.get('difficulty', 'N/A')}/5\n\n"
    )
    return meta_prefix + review_text


def preprocess_rmp_file(raw_text: str) -> tuple[dict, list[str]]:
    """
    Full preprocessing pipeline for an RMP file.
    Returns (header_metadata, list_of_metadata_injected_reviews).
    """
    header = extract_rmp_header(raw_text)
    reviews = split_rmp_reviews(raw_text)
    enriched = [inject_metadata_into_review(r, header) for r in reviews]

    logger.debug(f"RMP enriched: {enriched}")

    return header, enriched


# ---------------------------------------------------------------------------
# Reddit preprocessing — pure Python
# ---------------------------------------------------------------------------

@dataclass
class _Comment:
    author: str
    text: str
    parent_author: str = ""
    children: list["_Comment"] = field(default_factory=list)


def _detect_indent_unit(lines: list[str]) -> int:
    """
    Infer the base indentation unit (in spaces) used for reply nesting.
    Looks at the smallest non-zero indent found on comment-starting lines.
    Falls back to 4 if no indented comments are present.
    """
    indents = [
        len(line) - len(line.lstrip())
        for line in lines
        if re.match(r"^\s+\[[^\]]+\]:", line)
    ]
    return min(indents) if indents else 4


def _parse_comment_tree(lines: list[str], indent_unit: int) -> list[_Comment]:
    """
    Parse a list of raw lines into a tree of _Comment objects.

    A line that matches ^\s*[author]: starts a new comment; its indentation
    level (spaces // indent_unit) determines its depth in the tree.
    Any other non-blank line is treated as a continuation of the most recent
    comment and appended to its text.
    """
    roots: list[_Comment] = []
    # Stack entries: (depth_level, _Comment)
    stack: list[tuple[int, _Comment]] = []
    current: Optional[_Comment] = None

    for line in lines:
        comment_match = re.match(r"^(\s*)\[([^\]]+)\]:\s*(.*)", line)
        if comment_match:
            indent = len(comment_match.group(1))
            level = indent // indent_unit
            author = comment_match.group(2).strip()
            text = comment_match.group(3).strip()

            # Pop stack entries that are at the same depth or deeper
            while stack and stack[-1][0] >= level:
                stack.pop()

            parent_author = stack[-1][1].author if stack else ""
            comment = _Comment(author=author, text=text, parent_author=parent_author)

            if not stack:
                roots.append(comment)
            else:
                stack[-1][1].children.append(comment)

            stack.append((level, comment))
            current = comment
        elif current is not None:
            stripped = line.strip()
            if stripped:
                current.text += "\n" + stripped

    return roots


def _render_comment_tree(comment: _Comment, is_root: bool = True) -> str:
    """
    Recursively render a comment and all its descendants into a single string.

    Root comments are rendered as:   [author]: text
    Replies are rendered as:         [author] (replying to [parent]): text
    """
    if is_root:
        header = f"[{comment.author}]:"
    else:
        header = f"[{comment.author}] (replying to [{comment.parent_author}]):"

    parts = [f"{header} {comment.text.strip()}"]

    for child in comment.children:
        parts.append(_render_comment_tree(child, is_root=False))

    return "\n\n".join(parts)


def _parse_reddit_raw(raw_text: str) -> dict:
    """
    Split a raw Reddit .txt file into its three structural parts:
    title, body (may be empty), and the raw comment lines.
    """
    title = ""
    body_lines: list[str] = []
    comment_lines: list[str] = []
    section = "header"

    for line in raw_text.splitlines():
        if line.startswith("SOURCE:"):
            continue
        elif line.startswith("POST TITLE:"):
            title = line.replace("POST TITLE:", "").strip()
            section = "title"
        elif line.startswith("POST BODY:"):
            section = "body"
            inline = line.replace("POST BODY:", "").strip()
            if inline:
                body_lines.append(inline)
        elif line.startswith("COMMENTS:"):
            section = "comments"
        elif section == "body":
            body_lines.append(line)
        elif section == "comments":
            comment_lines.append(line)

    return {
        "title": title,
        "body": "\n".join(body_lines).strip(),
        "comment_lines": comment_lines,
    }


def _split_body_blocks(title: str, body: str) -> list[str]:
    """
    Split a post body into blocks.

    If the body uses a course-bullet structure (lines starting with
    "- CS XXXX:" or "- MATH XXXX:"), each bullet becomes its own block
    with the post title prepended. This makes each course tip a discrete
    semantic unit — the same insight as treating each RMP review separately.

    If no such structure is detected, the body is returned as one block.
    """
    bullet_pattern = re.compile(
        r"^-\s*(?:CS|MATH)\s*\d{4}:", re.IGNORECASE | re.MULTILINE
    )
    positions = [m.start() for m in bullet_pattern.finditer(body)]

    # Not a course-bullet body — keep as single block
    if len(positions) < 2:
        return [f'[Post: "{title}"]\n\n{body}']

    # Split at each bullet boundary
    blocks = []
    for i, start in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(body)
        bullet_text = body[start:end].strip()
        blocks.append(f'[Post: "{title}"]\n\n{bullet_text}')

    logger.debug(f"Post body split into {len(blocks)} course-bullet blocks.")
    return blocks


def preprocess_reddit_file(raw_text: str) -> list[str]:
    """
    Full preprocessing pipeline for a Reddit .txt file.

    Returns a list of self-contained text blocks, one per top-level comment
    thread (plus one extra block for the post body, if present). Every block
    is prefixed with the post title so no chunk is ever orphaned from its topic.

    Each block is then independently chunked by chunk_reddit_post(), which
    means the recursive splitter never cuts across two unrelated threads.

    Why blocks instead of one flat string?
    - Preserves the natural semantic unit: one opinion thread per block.
    - Prevents the chunker from merging unrelated comments into the same chunk.
    - Short comments become single chunks naturally; long ones are split only
      within their own thread.
    """
    parsed = _parse_reddit_raw(raw_text)
    title = parsed["title"]
    body = parsed["body"]
    comment_lines = parsed["comment_lines"]

    indent_unit = _detect_indent_unit(comment_lines)
    top_level_comments = _parse_comment_tree(comment_lines, indent_unit)

    blocks: list[str] = []

    # Post body (if present): split into per-course blocks if it uses a
    # course bullet structure (- CS XXXX: ...), otherwise keep as one block.
    if body:
        blocks.extend(_split_body_blocks(title, body))

    # Each top-level comment + its full reply chain becomes one block
    for comment in top_level_comments:
        rendered = _render_comment_tree(comment, is_root=True)
        blocks.append(f'[Thread from post: "{title}"]\n\n{rendered}')

    logger.debug(f"Reddit '{title}': {len(blocks)} blocks from {len(top_level_comments)} top-level comments")
    return blocks


# ---------------------------------------------------------------------------
# UoPeople preprocessing
# ---------------------------------------------------------------------------

def normalize_course_code(code: str) -> str:
    """
    Normalize course codes to a consistent format without spaces (e.g. 'CS 1101' -> 'CS1101').
    """
    return re.sub(r"\s+", "", code.strip().upper())


def preprocess_uop_catalog_file(raw_text: str) -> str:
    """
    Light normalization for the UoPeople degree catalog.
    No LLM needed — the document is already well-structured.
    Returns the cleaned text ready for recursive chunking.
    """
    # Normalize course code references (e.g. CS 1101 -> CS1101) for consistent filtering later
    normalized = re.sub(r"\b([A-Z]{2})\s+(\d{4})\b", r"\1\2", raw_text)
    return normalized.strip()


def preprocess_uop_course_list_file(raw_text: str) -> str:
    """
    Light normalization for the UoPeople course list.
    Returns the cleaned text ready for structure-based chunking.
    """
    normalized = re.sub(r"\b([A-Z]{2})\s+(\d{4})\b", r"\1\2", raw_text)
    return normalized.strip()
