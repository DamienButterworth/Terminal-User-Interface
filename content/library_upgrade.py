from __future__ import annotations

import os
import re
from difflib import unified_diff
from typing import TYPE_CHECKING, Dict, Optional, List

from textual import on, work
from textual.containers import VerticalScroll
from textual.widgets import Label, Button, TextArea, Checkbox
from textual_fspicker import SelectDirectory

from .multi_file_diff_viewer import MultiFileDiffViewer

if TYPE_CHECKING:
    from main import ContentRouter


# ---------------------------------------------------------------------
# Version helper
# ---------------------------------------------------------------------

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


# ---------------------------------------------------------------------
# Lossless search + replace helper
# ---------------------------------------------------------------------

def lossless_upgrade(original: str, group: str, artifact: str,
                     new_version: str, threshold_enabled: bool) -> tuple[str, bool]:
    """
    Perform lossless (whitespace-preserving) version upgrades without touching formatting.
    Returns (modified_text, upgraded_bool)
    """

    # Regex to match EXACT dependency including all surrounding whitespace
    # Example matched:
    #   "org.mockito"   %   "mockito-core"   %   "5.20.0"
    pattern = re.compile(
        rf'("{re.escape(group)}"\s*%%?\s*"{re.escape(artifact)}"\s*%\s*)"([^"]+)"'
    )

    modified = original
    upgraded_any = False
    last_end = 0
    result_parts = []

    for m in pattern.finditer(original):
        before = original[last_end:m.start()]
        result_parts.append(before)

        full_prefix = m.group(1)
        old_version = m.group(2)

        old_tuple = parse_version(old_version)
        new_tuple = parse_version(new_version)

        # Threshold check
        if threshold_enabled and old_tuple > new_tuple:
            # Keep original
            result_parts.append(m.group(0))
        else:
            # Upgrade ONLY the version literal — preserve formatting
            result_parts.append(f'{full_prefix}"{new_version}"')
            upgraded_any = True

        last_end = m.end()

    # Remainder
    result_parts.append(original[last_end:])

    if upgraded_any:
        modified = "".join(result_parts)

    return modified, upgraded_any


# ---------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------

class LibraryUpgradeContent(VerticalScroll):

    def __init__(self):
        super().__init__()
        self.root_dir: Optional[str] = "/Users/damien.butterworth/WORKSPACE"

    @property
    def app(self) -> "ContentRouter":
        return super().app

    # --------------------------------------------------------------
    def compose(self):
        yield Label("Library Upgrade Tool", classes="title")

        yield Button("Select Directory", id="pick_dir")
        yield Label(f"Directory: {self.root_dir}", id="dir_label")

        yield Label("Libraries to upgrade (group:artifact:version):")
        yield TextArea(
            id="libs_input",
            placeholder="org.mockito:mockito-core:6.1.2\norg.scalatest:scalatest:3.2.19",
            text=""
        )

        yield Checkbox("Only upgrade versions ≤ new version", id="version_threshold")

        yield Button("Preview Upgrade", id="preview")
        yield Button("Apply Upgrade", id="apply")

    # --------------------------------------------------------------
    @on(Button.Pressed, "#pick_dir")
    @work
    async def pick_directory(self):
        directory = await self.app.push_screen_wait(SelectDirectory())
        if directory:
            self.root_dir = directory
            self.query_one("#dir_label", Label).update(f"Directory: {directory}")

    # --------------------------------------------------------------
    def parse_libraries(self) -> list[dict]:
        raw = self.query_one("#libs_input", TextArea).text
        libs = []

        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(":")
            if len(parts) != 3:
                self.app.notify(f"Invalid format: {line}", severity="warning")
                continue

            group, artifact, version = parts
            libs.append({
                "group": group.strip(),
                "artifact": artifact.strip(),
                "version": version.strip(),
                "version_tuple": parse_version(version.strip())
            })

        return libs

    # --------------------------------------------------------------
    @on(Button.Pressed, "#preview")
    @work
    async def preview(self):
        await self._upgrade(preview=True)

    @on(Button.Pressed, "#apply")
    @work
    async def apply(self):
        await self._upgrade(preview=False)

    # --------------------------------------------------------------
    async def _upgrade(self, preview: bool):
        if not self.root_dir:
            self.app.notify("Select a directory first.", severity="warning")
            return

        libs = self.parse_libraries()
        if not libs:
            self.app.notify("Enter at least one library.", severity="warning")
            return

        threshold_enabled = self.query_one("#version_threshold", Checkbox).value

        diff_map: Dict[str, str] = {}
        writes: List[tuple[str, str]] = []

        # Traverse files
        for subdir, _, files in os.walk(self.root_dir):
            for fn in files:
                if not (fn.endswith(".scala") or fn.endswith(".sbt")):
                    continue

                path = os.path.join(subdir, fn)
                try:
                    original = open(path, "r", encoding="utf-8").read()
                except:
                    continue

                modified = original
                upgraded = False

                # Apply each library's upgrade
                for lib in libs:
                    modified, changed = lossless_upgrade(
                        modified,
                        lib["group"],
                        lib["artifact"],
                        lib["version"],
                        threshold_enabled
                    )
                    if changed:
                        upgraded = True

                if not upgraded:
                    continue

                relative = os.path.relpath(path, self.root_dir)

                if preview:
                    diff = "\n".join(unified_diff(
                        original.splitlines(),
                        modified.splitlines(),
                        fromfile=relative,
                        tofile=f"{relative} (modified)"
                    ))
                    diff_map[relative] = diff
                else:
                    writes.append((path, modified))

        # PREVIEW
        if preview:
            if not diff_map:
                self.app.notify("No changes detected.", severity="warning")
                return

            self.app.show_in_content(MultiFileDiffViewer(diff_map))
            return

        # APPLY
        for path, content in writes:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

        self.app.notify(f"Applied changes to {len(writes)} files.", severity="success")
