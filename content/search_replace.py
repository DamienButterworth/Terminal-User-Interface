from __future__ import annotations

import asyncio
import os
import re
from difflib import unified_diff, SequenceMatcher
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from textual import on, work
from textual.containers import VerticalScroll
from textual.widgets import Button, Checkbox, Input, Label
from textual_fspicker import SelectDirectory

if TYPE_CHECKING:
    from main import ContentRouter


# ============================================================================
# Helpers
# ============================================================================

def is_text_file(path: str) -> bool:
    """Skip binary files."""
    try:
        with open(path, "rb") as f:
            return b"\0" not in f.read(8000)
    except Exception:
        return False


def remove_ws(s: str) -> str:
    return re.sub(r"\s+", "", s)


# ============================================================================
# Tokenisation (Minimal-Diff Mode)
# ============================================================================

TOKEN_PATTERN = re.compile(
    r"""
        "[^"]*"                |   # quoted strings
        '[^']*'                |   # single-quoted
        [%(){}\[\],=]          |   # punctuation
        [A-Za-z0-9._:-]+           # identifiers/versions
    """,
    re.VERBOSE,
)


def tokenize(s: str) -> List[str]:
    return TOKEN_PATTERN.findall(s)


def align_tokens(old: List[str], new: List[str]) -> List[Tuple[str, Any]]:
    """Align token sequences and emit operations."""
    ops = []
    sm = SequenceMatcher(a=old, b=new)

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for tok in old[i1:i2]:
                ops.append(("equal", tok))
        elif tag == "replace":
            o, n = old[i1:i2], new[j1:j2]
            if len(o) == len(n):
                for oo, nn in zip(o, n):
                    ops.append(("replace", oo, nn))
            else:
                ops.append(("replace", o, n))
        elif tag == "delete":
            for tok in old[i1:i2]:
                ops.append(("delete", tok))
        elif tag == "insert":
            for tok in new[j1:j2]:
                ops.append(("insert", tok))

    return ops


def find_token_positions(content: str, tokens: List[str]) -> Optional[List[Tuple[int, int]]]:
    """Locate tokens in content in order."""
    positions = []
    idx = 0

    for tok in tokens:
        while idx < len(content) and content[idx].isspace():
            idx += 1

        pos = content.find(tok, idx)
        if pos == -1:
            return None

        positions.append((pos, pos + len(tok)))
        idx = pos + len(tok)

    return positions


# ============================================================================
# Full-replacement logic
# ============================================================================

def find_matches(content: str, search: str, use_regex: bool) -> List[Tuple[int, int]]:
    content_now = remove_ws(content)
    search_now = remove_ws(search)
    matches = []

    if use_regex:
        patt = re.compile(search_now)
        for m in patt.finditer(content_now):
            matches.append((m.start(), m.end()))
    else:
        pos = content_now.find(search_now)
        while pos != -1:
            matches.append((pos, pos + len(search_now)))
            pos = content_now.find(search_now, pos + 1)

    return matches


def build_index_reverse_map(content: str) -> List[int]:
    return [i for i, ch in enumerate(content) if not ch.isspace()]


# ============================================================================
# Diff generator — list of lines
# ============================================================================

def generate_diff_lines(original: str, modified: str, filename: str) -> List[str]:
    return list(unified_diff(
        original.splitlines(keepends=False),
        modified.splitlines(keepends=False),
        fromfile=f"{filename} (original)",
        tofile=f"{filename} (modified)",
    ))


# ============================================================================
# File Processor
# ============================================================================

def process_file(
    path: str,
    search: str,
    replace: str,
    use_regex: bool,
    preview: bool,
    minimal_diff: bool,
) -> Optional[Dict[str, Any]]:

    if not is_text_file(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return None

    # ----------------------------------------------------------------------
    # MINIMAL TOKEN DIFF MODE
    # ----------------------------------------------------------------------
    if minimal_diff:
        old_tokens = tokenize(search)
        new_tokens = tokenize(replace)

        # Ensure match exists
        if remove_ws(content).find(remove_ws(search)) == -1:
            return None

        positions = find_token_positions(content, old_tokens)
        if not positions:
            return None

        ops = align_tokens(old_tokens, new_tokens)

        modified = list(content)

        for op in ops:
            if op[0] == "replace":
                old_tok, new_tok = op[1], op[2]
                pos = content.find(old_tok)
                if pos != -1:
                    modified[pos:pos + len(old_tok)] = new_tok

        modified_str = "".join(modified)

        if preview:
            diff_lines = generate_diff_lines(content, modified_str, os.path.relpath(path))
            return {
                "file": path,
                "preview": True,
                "replacements": 1,
                "diff": {"lines": diff_lines},
            }

        with open(path, "w", encoding="utf-8") as f:
            f.write(modified_str)

        return {"file": path, "preview": False, "replacements": 1}

    # ----------------------------------------------------------------------
    # FULL MATCH MODE
    # ----------------------------------------------------------------------
    mapping = build_index_reverse_map(content)
    matches = find_matches(content, search, use_regex)

    if not matches:
        return None

    modified = content

    for start_now, end_now in reversed(matches):
        sr = mapping[start_now]
        er = mapping[end_now - 1] + 1
        modified = modified[:sr] + replace + modified[er:]

    if preview:
        diff_lines = generate_diff_lines(content, modified, os.path.relpath(path))
        return {
            "file": path,
            "preview": True,
            "replacements": len(matches),
            "diff": {"lines": diff_lines},
        }

    with open(path, "w", encoding="utf-8") as f:
        f.write(modified)

    return {"file": path, "preview": False, "replacements": len(matches)}


# ============================================================================
# Parallel directory scanning
# ============================================================================

async def process_directory_parallel(
    root: str,
    search: str,
    replace: str,
    extensions: List[str],
    use_regex: bool,
    preview: bool,
    minimal_diff: bool,
    workers: int = 8,
):
    sem = asyncio.Semaphore(workers)
    tasks = []

    def ext_ok(fn: str):
        return True if not extensions else any(fn.endswith(ext) for ext in extensions)

    for subdir, _, files in os.walk(root):
        for fn in files:
            if not ext_ok(fn):
                continue

            full_path = os.path.join(subdir, fn)

            async def run_file(p=full_path):
                async with sem:
                    return await asyncio.to_thread(
                        process_file, p, search, replace,
                        use_regex, preview, minimal_diff
                    )

            tasks.append(asyncio.create_task(run_file()))

    results = await asyncio.gather(*tasks)
    return [r for r in results if r]


# ============================================================================
# TEXTUAL UI
# ============================================================================

class SearchReplaceContent(VerticalScroll):

    def __init__(self):
        super().__init__()
        self.root_dir: Optional[str] = None

    @property
    def app(self) -> "ContentRouter":  # type: ignore
        return super().app

    def compose(self):
        yield Label("Recursive Search & Replace (Diff Viewer Enabled)", classes="title")

        yield Button("Select Directory", id="pick_dir")
        yield Label("No directory selected", id="dir_label")

        yield Label("File Extensions (.scala,.sbt,.json):")
        yield Input(".scala,.sbt,.txt,.json", id="ext_filter")

        yield Label("Search String:")
        yield Input(id="search")

        yield Label("Replacement String:")
        yield Input(id="replace")

        yield Checkbox("Use Regex", id="use_regex")
        yield Checkbox("Preview Mode", id="preview")
        yield Checkbox("Minimal Token-Diff Mode (preserve whitespace)", id="minimal_diff")

        yield Button("Run", id="run", classes="action")

    # -------------------------------------------- Directory Picker
    @on(Button.Pressed, "#pick_dir")
    @work
    async def pick_directory(self):
        directory = await self.app.push_screen_wait(SelectDirectory())
        lbl = self.query_one("#dir_label", Label)

        if directory:
            self.root_dir = directory
            lbl.update(f"Selected: {directory}")
        else:
            lbl.update("No directory selected")

    # -------------------------------------------- Execute Search/Replace
    @on(Button.Pressed, "#run")
    @work
    async def run_process(self):
        if not self.root_dir:
            self.app.notify("Select a directory first.", severity="warning")
            return

        search = self.query_one("#search", Input).value.strip()
        replace = self.query_one("#replace", Input).value.strip()
        use_regex = self.query_one("#use_regex", Checkbox).value
        preview = self.query_one("#preview", Checkbox).value
        minimal_diff = self.query_one("#minimal_diff", Checkbox).value

        if not search:
            self.app.notify("Search string required.", severity="warning")
            return

        ext_raw = self.query_one("#ext_filter", Input).value.strip()
        extensions = [e.strip() for e in ext_raw.split(",")] if ext_raw else []

        self.app.notify(
            f"Running {'Preview' if preview else 'Apply'} "
            f"({'Minimal Token-Diff' if minimal_diff else 'Full Replace'})...",
            severity="information"
        )

        results = await process_directory_parallel(
            self.root_dir, search, replace,
            extensions, use_regex, preview,
            minimal_diff, workers=8
        )

        # --- Show DIFF VIEWER if preview ---
        if preview and results:
            from .diff_viewer import DiffViewer
            first = results[0]
            diff_lines = first["diff"]["lines"]
            diff_text = "\n".join(diff_lines)

            self.app.show_in_content(DiffViewer(diff_text))
            return

        # --- Otherwise, show JSON summary ---
        payload = {
            "directory": self.root_dir,
            "preview": preview,
            "minimal_diff": minimal_diff,
            "extensions": extensions,
            "results_count": len(results),
            "results": results,
        }

        from .json_render import JsonRender
        self.app.show_in_content(JsonRender(payload, "search_replace_results", "file"))

        self.app.notify(
            f"Completed. {len(results)} file(s) affected.",
            severity="success"
        )
