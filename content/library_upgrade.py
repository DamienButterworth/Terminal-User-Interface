from __future__ import annotations

import os
import re
from difflib import unified_diff
from typing import TYPE_CHECKING, Dict, Optional, List

from textual import on, work
from textual.containers import VerticalScroll
from textual.widgets import Label, Button, Input, Checkbox
from textual_fspicker import SelectDirectory

from .multi_file_diff_viewer import MultiFileDiffViewer

if TYPE_CHECKING:
    from main import ContentRouter


# -------------------------
# Version helpers
# -------------------------

def parse_version(v: str) -> tuple[int, int, int]:
    v = v.split("-")[0]
    parts = v.split(".")
    nums = []

    for p in parts:
        if p.isdigit():
            nums.append(int(p))
        else:
            m = re.match(r"(\d+)", p)
            nums.append(int(m.group(1)) if m else 0)

    while len(nums) < 3:
        nums.append(0)

    return tuple(nums[:3])


# -------------------------
# Tokeniser
# -------------------------

TOKEN_PATTERN = re.compile(
    r"""
        "[^"]*"                |
        '[^']*'                |
        [%(){}\[\],=]          |
        [A-Za-z0-9._:-]+
    """,
    re.VERBOSE,
)

def tokenize(s: str) -> List[str]:
    return TOKEN_PATTERN.findall(s)


# -------------------------
# Library Upgrade UI
# -------------------------

class LibraryUpgradeContent(VerticalScroll):

    def __init__(self):
        super().__init__()
        self.root_dir: Optional[str] = "/Users/damien.butterworth/WORKSPACE"

    @property
    def app(self) -> "ContentRouter":
        return super().app

    def compose(self):
        yield Label("Library Upgrade Tool", classes="title")

        yield Button("Select Directory", id="pick_dir")
        yield Label(f"Directory: {self.root_dir}", id="dir_label")

        yield Label("Group ID:")
        yield Input(id="group_id")

        yield Label("Artifact ID:")
        yield Input(id="artifact_id")

        yield Label("Upgrade To Version:")
        yield Input(id="new_version")

        yield Checkbox("Only upgrade versions ≤ new version", id="version_threshold")

        yield Button("Scan for Versions", id="scan")
        yield Button("Preview Upgrade", id="preview")
        yield Button("Apply Upgrade", id="apply")

    # -------------------------
    @on(Button.Pressed, "#pick_dir")
    @work
    async def pick_directory(self):
        directory = await self.app.push_screen_wait(SelectDirectory())
        lbl = self.query_one("#dir_label", Label)

        if directory:
            self.root_dir = directory
            lbl.update(f"Directory: {directory}")

    # -------------------------
    @on(Button.Pressed, "#scan")
    @work
    async def scan_versions(self):
        if not self.root_dir:
            self.app.notify("Select directory first.", severity="warning")
            return

        group = self.query_one("#group_id", Input).value.strip()
        artifact = self.query_one("#artifact_id", Input).value.strip()

        if not group or not artifact:
            self.app.notify("Group and Artifact required.", severity="warning")
            return

        versions: Dict[str, int] = {}

        for subdir, _, files in os.walk(self.root_dir):
            for fn in files:
                if not (fn.endswith(".scala") or fn.endswith(".sbt")):
                    continue

                path = os.path.join(subdir, fn)

                try:
                    content = open(path, "r", encoding="utf-8").read()
                except:
                    continue

                tokens = tokenize(content)

                for i in range(len(tokens) - 4):
                    if (
                        tokens[i] == f"\"{group}\""
                        and tokens[i+1] == "%"
                        and tokens[i+2] == f"\"{artifact}\""
                        and tokens[i+3] == "%"
                    ):
                        ver = tokens[i+4].strip('"')
                        versions[ver] = versions.get(ver, 0) + 1

        from .json_render import JsonRender
        self.app.show_in_content({
            "directory": self.root_dir,
            "group": group,
            "artifact": artifact,
            "versions_found": versions,
        })

    # -------------------------
    @on(Button.Pressed, "#preview")
    @work
    async def preview(self):
        await self._upgrade(preview=True)

    @on(Button.Pressed, "#apply")
    @work
    async def apply(self):
        await self._upgrade(preview=False)

    # -------------------------

    async def _upgrade(self, preview: bool):
        if not self.root_dir:
            self.app.notify("Select directory first.", severity="warning")
            return

        group = self.query_one("#group_id", Input).value.strip()
        artifact = self.query_one("#artifact_id", Input).value.strip()
        new_version = self.query_one("#new_version", Input).value.strip()
        threshold_enabled = self.query_one("#version_threshold", Checkbox).value

        if not group or not artifact or not new_version:
            self.app.notify("Group, Artifact, New Version required.", severity="warning")
            return

        new_version_tuple = parse_version(new_version)
        new_token = f"\"{new_version}\""

        diff_map: Dict[str, str] = {}
        writes: List[tuple[str, str]] = []

        for subdir, _, files in os.walk(self.root_dir):
            for fn in files:
                if not (fn.endswith(".scala") or fn.endswith(".sbt")):
                    continue

                path = os.path.join(subdir, fn)

                try:
                    original = open(path, "r", encoding="utf-8").read()
                except:
                    continue

                tokens = tokenize(original)
                modified = original
                upgraded = False

                for i in range(len(tokens) - 4):
                    if (
                        tokens[i] == f"\"{group}\""
                        and tokens[i+1] == "%"
                        and tokens[i+2] == f"\"{artifact}\""
                        and tokens[i+3] == "%"
                    ):
                        old_tok = tokens[i+4]
                        old_ver = old_tok.strip('"')
                        old_tuple = parse_version(old_ver)

                        if threshold_enabled and old_tuple > new_version_tuple:
                            continue

                        modified = modified.replace(old_tok, new_token)
                        upgraded = True

                if not upgraded:
                    continue

                relative = os.path.relpath(path, self.root_dir)

                if preview:
                    diff = "\n".join(unified_diff(
                        original.splitlines(),
                        modified.splitlines(),
                        fromfile=relative,
                        tofile=f"{relative} (modified)",
                    ))
                    diff_map[relative] = diff
                else:
                    writes.append((path, modified))

        if preview:
            if not diff_map:
                self.app.notify("No changes detected.", severity="warning")
                return

            self.app.show_in_content(MultiFileDiffViewer(diff_map))
            return

        for path, content in writes:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
            except:
                pass

        self.app.notify(f"Applied changes to {len(writes)} files.", severity="success")
