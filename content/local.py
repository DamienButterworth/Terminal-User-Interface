from textual.widgets import Static, Label, Button

from config import YAMLConfig


class LocalContent(Static):

    def __init__(self):
        super().__init__()

    def compose(self):
        yield Label("Local", classes="section")