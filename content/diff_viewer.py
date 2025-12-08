from textual.widgets import Static
from textual.containers import VerticalScroll
from textual.app import ComposeResult


class DiffViewer(VerticalScroll):
    """
    Colourised, scrollable diff viewer compatible with all Textual versions.
    """

    def __init__(self, diff_text: str):
        super().__init__()
        self.diff_text = diff_text or ""

    def colorise(self, text: str) -> str:
        """Apply Rich markup to diff lines."""
        coloured_lines = []

        for line in text.splitlines():
            if line.startswith("+++"):
                coloured_lines.append(f"[bold white]{line}[/]")
            elif line.startswith("---"):
                coloured_lines.append(f"[bold white]{line}[/]")
            elif line.startswith("@@"):
                coloured_lines.append(f"[cyan]{line}[/]")
            elif line.startswith("+"):
                coloured_lines.append(f"[green]{line}[/]")
            elif line.startswith("-"):
                coloured_lines.append(f"[red]{line}[/]")
            else:
                # context lines
                coloured_lines.append(f"[dim]{line}[/]")

        return "\n".join(coloured_lines)

    def compose(self) -> ComposeResult:
        if not self.diff_text.strip():
            yield Static("No changes in this file.", markup=False)
            return

        # Apply colouring
        coloured = self.colorise(self.diff_text)

        # Pad to avoid wrapping → enable horizontal scrolling
        padded_lines = [" " + l for l in coloured.splitlines()]
        widest = max(len(l) for l in padded_lines)
        padded = "\n".join(padded_lines)

        text = Static(padded, markup=True)
        text.styles.width = "auto"
        text.styles.min_width = widest + 2

        yield text
