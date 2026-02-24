from textual.widgets import Markdown

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()


class HomeContent(Markdown):
    def __init__(self):
        with open(PROJECT_ROOT / "content" / "home.md", "r", encoding="utf-8") as f:
            markdown_text = f.read()

        super().__init__(markdown_text)

