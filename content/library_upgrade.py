from __future__ import annotations

import asyncio
import os
import re
import subprocess
from difflib import unified_diff
from typing import TYPE_CHECKING, Dict, Optional, List, Set, Tuple

from textual import on, work
from textual.containers import VerticalScroll
from textual.widgets import Label, Button, TextArea, Checkbox
from textual_fspicker import SelectDirectory

from .multi_file_diff_viewer import MultiFileDiffViewer

if TYPE_CHECKING:
    from main import ContentRouter



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


def is_major_bump(old_version: str, new_version: str) -> bool:
    """Return True if the new version has a higher major component."""
    old_major = parse_version(old_version)[0]
    new_major = parse_version(new_version)[0]
    return new_major > old_major


def lossless_upgrade(original: str, group: str, artifact: str,
                     new_version: str, threshold_enabled: bool,
                     skip_major: bool = False) -> tuple[str, bool]:
    """
    Perform lossless (whitespace-preserving) version upgrades for INLINE
    string-literal versions.
    Returns (modified_text, upgraded_bool)
    """

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

        if threshold_enabled and old_tuple > new_tuple:
            result_parts.append(m.group(0))
        elif skip_major and is_major_bump(old_version, new_version):
            result_parts.append(m.group(0))
        else:
            result_parts.append(f'{full_prefix}"{new_version}"')
            upgraded_any = True

        last_end = m.end()

    result_parts.append(original[last_end:])

    if upgraded_any:
        modified = "".join(result_parts)

    return modified, upgraded_any


def lossless_upgrade_variable_refs(
    original: str,
    group: str,
    artifact: str,
    new_version: str,
    threshold_enabled: bool,
    skip_major: bool = False,
) -> tuple[str, bool, list[str]]:
    """
    Handle dependency declarations that use a variable reference for the version:
        "uk.gov.hmrc.mongo" %% "hmrc-mongo-play-30" % mongoVersion

    Finds the variable name, locates its val/def definition in the same file,
    and upgrades the string literal there.

    Returns (modified_text, upgraded_bool, list_of_warnings)
    """

    dep_pattern = re.compile(
        rf'"{re.escape(group)}"\s*%%?\s*"{re.escape(artifact)}"\s*%\s*'
        r'(?!")([a-zA-Z_]\w*)'
    )

    warnings: list[str] = []
    var_names: Set[str] = set()

    for m in dep_pattern.finditer(original):
        var_names.add(m.group(1))

    if not var_names:
        return original, False, warnings

    modified = original
    upgraded_any = False

    for var_name in var_names:
        val_pattern = re.compile(
            rf'((?:private\s+)?(?:lazy\s+)?(?:val|def)\s+{re.escape(var_name)}\s*(?::\s*String\s*)?=\s*)"([^"]+)"'
        )

        val_match = val_pattern.search(modified)
        if not val_match:
            warnings.append(
                f"Variable '{var_name}' used for {group}:{artifact} "
                f"but its definition was not found in this file."
            )
            continue

        old_version = val_match.group(2)
        old_tuple = parse_version(old_version)
        new_tuple = parse_version(new_version)

        if threshold_enabled and old_tuple > new_tuple:
            continue

        if skip_major and is_major_bump(old_version, new_version):
            continue

        prefix = val_match.group(1)
        replacement = f'{prefix}"{new_version}"'
        modified = modified[:val_match.start()] + replacement + modified[val_match.end():]
        upgraded_any = True

    return modified, upgraded_any, warnings

def find_git_root(path: str) -> Optional[str]:
    """Walk up from path to find the nearest .git directory. Returns the repo root or None."""
    current = os.path.abspath(path)
    while True:
        if os.path.isdir(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def run_git(args: list[str], cwd: str) -> tuple[int, str, str]:
    """Run a git command in the given directory. Returns (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def branch_exists(branch: str, cwd: str) -> bool:
    """Return True if the branch already exists locally or remotely."""
    code, out, _ = run_git(["branch", "--list", branch], cwd)
    if out:
        return True
    code, out, _ = run_git(["ls-remote", "--heads", "origin", branch], cwd)
    return bool(out)


def make_unique_branch_name(base: str, cwd: str) -> str:
    """Return base if it doesn't exist, otherwise base-2, base-3, etc."""
    if not branch_exists(base, cwd):
        return base
    counter = 2
    while True:
        candidate = f"{base}-{counter}"
        if not branch_exists(candidate, cwd):
            return candidate
        counter += 1


def build_branch_name(libs: list[dict]) -> str:
    """Build a branch name from the list of libraries being upgraded."""
    parts = [f"{lib['artifact']}-{lib['version']}" for lib in libs]
    name = "upgrade-" + "_".join(parts)
    name = re.sub(r"[^a-zA-Z0-9._/-]", "-", name)
    return name


def build_commit_message(libs: list[dict]) -> str:
    """Build a descriptive commit message listing all upgraded libraries."""
    if len(libs) == 1:
        lib = libs[0]
        title = f"Upgrade {lib['artifact']} to {lib['version']}"
        body = f"Bumps {lib['group']}:{lib['artifact']} to version {lib['version']}."
    else:
        title = "Upgrade libraries: " + ", ".join(
            f"{lib['artifact']} → {lib['version']}" for lib in libs
        )
        lines = ["Bumps the following dependencies:"]
        for lib in libs:
            lines.append(f"  - {lib['group']}:{lib['artifact']} → {lib['version']}")
        body = "\n".join(lines)

    return f"{title}\n\n{body}"


def build_pr_body(libs: list[dict]) -> str:
    """Build a PR description body."""
    lines = ["## Library Upgrades", ""]
    lines.append("| Group | Artifact | New Version |")
    lines.append("|-------|----------|-------------|")
    for lib in libs:
        lines.append(f"| `{lib['group']}` | `{lib['artifact']}` | `{lib['version']}` |")
    return "\n".join(lines)


async def git_workflow(
    repo_root: str,
    changed_files: list[str],
    libs: list[dict],
) -> tuple[bool, str]:
    """
    For a single repo:
      1. Create a uniquely-named branch off the current HEAD
      2. Stage only the changed files
      3. Commit with a descriptive message
      4. Push to origin
      5. Create a PR via `gh pr create`

    Returns (success: bool, message: str).
    """
    branch_base = build_branch_name(libs)
    branch = await asyncio.to_thread(make_unique_branch_name, branch_base, repo_root)

    code, _, err = await asyncio.to_thread(run_git, ["checkout", "-b", branch], repo_root)
    if code != 0:
        return False, f"Failed to create branch '{branch}': {err}"

    for f in changed_files:
        code, _, err = await asyncio.to_thread(run_git, ["add", f], repo_root)
        if code != 0:
            return False, f"Failed to stage '{f}': {err}"

    commit_msg = build_commit_message(libs)
    code, _, err = await asyncio.to_thread(run_git, ["commit", "-m", commit_msg], repo_root)
    if code != 0:
        return False, f"Failed to commit in '{repo_root}': {err}"

    code, _, err = await asyncio.to_thread(run_git, ["push", "-u", "origin", branch], repo_root)
    if code != 0:
        return False, f"Failed to push branch '{branch}': {err}"

    pr_title = commit_msg.splitlines()[0]
    pr_body = build_pr_body(libs)

    def create_pr():
        return subprocess.run(
            ["gh", "pr", "create",
             "--title", pr_title,
             "--body", pr_body,
             "--head", branch],
            cwd=repo_root,
            capture_output=True,
            text=True
        )

    gh_result = await asyncio.to_thread(create_pr)

    if gh_result.returncode != 0:
        return False, (
            f"Branch '{branch}' pushed but PR creation failed: "
            f"{gh_result.stderr.strip()}"
        )

    pr_url = gh_result.stdout.strip()
    return True, f"PR created for '{os.path.basename(repo_root)}': {pr_url}"

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

        yield Label("Libraries to upgrade (group:artifact:version):")
        yield TextArea(
            id="libs_input",
            placeholder="org.mockito:mockito-core:6.1.2\norg.scalatest:scalatest:3.2.19",
            text=""
        )

        yield Checkbox("Only upgrade versions ≤ new version", id="version_threshold")
        yield Checkbox("Skip major version upgrades", id="skip_major", value=True)

        yield Button("Preview Upgrade", id="preview")
        yield Button("Apply Upgrade", id="apply")

    def thread_notify(self, message: str, severity: str = "information") -> None:
        """Notify from within a @work worker (async workers run on the event loop)."""
        self.app.notify(message, severity=severity)

    @on(Button.Pressed, "#pick_dir")
    @work
    async def pick_directory(self):
        directory = await self.app.push_screen_wait(SelectDirectory())
        if directory:
            self.root_dir = directory
            self.query_one("#dir_label", Label).update(f"Directory: {directory}")

    def parse_libraries(self) -> list[dict]:
        raw = self.query_one("#libs_input", TextArea).text
        libs = []

        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(":")
            if len(parts) != 3:
                self.thread_notify(f"Invalid format: {line}", severity="warning")
                continue

            group, artifact, version = parts
            libs.append({
                "group": group.strip(),
                "artifact": artifact.strip(),
                "version": version.strip(),
                "version_tuple": parse_version(version.strip())
            })

        return libs

    @on(Button.Pressed, "#preview")
    @work
    async def preview(self):
        await self._upgrade(preview=True)

    @on(Button.Pressed, "#apply")
    @work
    async def apply(self):
        await self._upgrade(preview=False)

    async def _upgrade(self, preview: bool):
        if not self.root_dir:
            self.thread_notify("Select a directory first.", severity="warning")
            return

        libs = self.parse_libraries()
        if not libs:
            self.thread_notify("Enter at least one library.", severity="warning")
            return

        threshold_enabled = self.query_one("#version_threshold", Checkbox).value
        skip_major = self.query_one("#skip_major", Checkbox).value

        diff_map: Dict[str, str] = {}

        repo_writes: Dict[str, List[Tuple[str, str]]] = {}
        repo_changed_lib_keys: Dict[str, Set[str]] = {}
        all_warnings: List[str] = []

        for subdir, _, files in os.walk(self.root_dir):
            for fn in files:
                if not (fn.endswith(".scala") or fn.endswith(".sbt")):
                    continue

                path = os.path.join(subdir, fn)
                try:
                    original = open(path, "r", encoding="utf-8").read()
                except Exception:
                    continue

                modified = original
                upgraded = False
                file_changed_lib_keys: Set[str] = set()

                for lib in libs:
                    lib_key = f"{lib['group']}:{lib['artifact']}"

                    modified, changed_inline = lossless_upgrade(
                        modified,
                        lib["group"],
                        lib["artifact"],
                        lib["version"],
                        threshold_enabled,
                        skip_major
                    )
                    if changed_inline:
                        upgraded = True
                        file_changed_lib_keys.add(lib_key)

                    modified, changed_var, warnings = lossless_upgrade_variable_refs(
                        modified,
                        lib["group"],
                        lib["artifact"],
                        lib["version"],
                        threshold_enabled,
                        skip_major
                    )
                    if changed_var:
                        upgraded = True
                        file_changed_lib_keys.add(lib_key)

                    relative = os.path.relpath(path, self.root_dir)
                    for w in warnings:
                        all_warnings.append(f"{relative}: {w}")

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
                    repo_root = find_git_root(path)
                    if repo_root not in repo_writes:
                        repo_writes[repo_root] = []
                        repo_changed_lib_keys[repo_root] = set()
                    repo_writes[repo_root].append((path, modified))
                    repo_changed_lib_keys[repo_root].update(file_changed_lib_keys)


        for w in all_warnings:
            self.thread_notify(w, severity="warning")

        if preview:
            if not diff_map:
                self.thread_notify("No changes detected.", severity="warning")
                return
            self.app.show_in_content(MultiFileDiffViewer(diff_map))
            return

        if not repo_writes:
            self.thread_notify("No changes detected.", severity="warning")
            return

        lib_by_key = {f"{lib['group']}:{lib['artifact']}": lib for lib in libs}

        total_files = 0
        for repo_root, writes in repo_writes.items():
            for fpath, content in writes:
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)
                total_files += 1

            if repo_root is None:
                self.thread_notify(
                    f"Wrote {len(writes)} file(s) outside any git repo (no branch/PR created).",
                    severity="warning"
                )
                continue

            changed_keys = repo_changed_lib_keys.get(repo_root, set())
            applied_libs = [lib_by_key[k] for k in changed_keys if k in lib_by_key]

            changed_paths = [p for p, _ in writes]
            self.thread_notify(f"Creating branch and PR for '{os.path.basename(repo_root)}'…")
            success, message = await git_workflow(repo_root, changed_paths, applied_libs)

            if success:
                self.thread_notify(message, severity="success")
            else:
                self.thread_notify(message, severity="error")

        self.thread_notify(
            f"Applied changes to {total_files} file(s) across {len(repo_writes)} repo(s).",
            severity="success"
        )