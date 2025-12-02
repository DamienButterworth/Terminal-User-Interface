from textual.widgets import Markdown


class HomeContent(Markdown):
    def __init__(self):
        with open("content/home.md", "r", encoding="utf-8") as f:
            markdown_text = f.read()

        super().__init__(markdown_text)

