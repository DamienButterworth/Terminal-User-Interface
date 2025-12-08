from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Label, ListView, ListItem, Static
from textual import on
from textual.app import ComposeResult

from .diff_viewer import DiffViewer


class MultiFileDiffViewer(Horizontal):
    """Left: file list. Middle: divider. Right: diff viewer."""

    def __init__(self, diffs: dict[str, str]):
        super().__init__(id="mfd_root")
        self.diffs = diffs
        self.paths = list(diffs.keys())   # <--- FIX: store paths by index

    def compose(self) -> ComposeResult:
        # LEFT pane
        with VerticalScroll(id="file_list_container"):
            yield ListView(id="file_list")

        # MIDDLE divider
        yield Static("│", id="divider")

        # RIGHT pane
        yield VerticalScroll(id="diff_panel")

    async def on_mount(self) -> None:
        # Layout sizing
        self.styles.width = "100%"
        self.styles.height = "100%"

        file_list_container = self.query_one("#file_list_container")
        file_list_container.styles.width = "30%"

        divider = self.query_one("#divider")
        divider.styles.width = 1
        divider.styles.height = "100%"

        diff_panel = self.query_one("#diff_panel")
        diff_panel.styles.width = "70%"
        diff_panel.styles.overflow_x = "auto"

        # Populate ListView VISUALLY
        file_list = self.query_one("#file_list", ListView)

        for rel_path in self.paths:
            file_list.append(ListItem(Label(rel_path)))

        if file_list.children:
            file_list.index = 0
            await self._show_diff_for_index(0)

    async def _show_diff_for_index(self, index: int):
        """Display diff based on index rather than label text."""
        # FIX: Use the stored path list instead of parsing the Label
        filepath = self.paths[index]

        diff_text = self.diffs.get(filepath, "")

        diff_panel = self.query_one("#diff_panel")
        diff_panel.remove_children()

        viewer = DiffViewer(diff_text)
        diff_panel.mount(viewer)

    @on(ListView.Selected, "#file_list")
    async def show_diff(self, event: ListView.Selected):
        await self._show_diff_for_index(event.list_view.index)
