import json
from textual import on
from textual.app import ComposeResult
from textual.widgets import Button
from textual.containers import VerticalScroll

from services.json_tree_viewer import JsonTreeViewer


class JsonRender(VerticalScroll):
    def __init__(
            self,
            data,
            title,
            label_keys=None,
            pre_label_key="",
            post_label_key="",
    ):
        super().__init__()
        self.data = data
        self.title = title
        self.label_keys = label_keys or {}
        self.pre_label_key = pre_label_key
        self.post_label_key = post_label_key

    def compose(self) -> ComposeResult:
        yield Button("📋 Copy JSON", id="copy_json")

        yield JsonTreeViewer(
            self.data,
            title=self.title,
            label_keys=self.label_keys,
            pre_label_key=self.pre_label_key,
            post_label_key=self.post_label_key,
        )

    @on(Button.Pressed, "#copy_json")
    async def copy_json(self) -> None:

        try:
            text = json.dumps(self.data, indent=2)
        except Exception:
            text = str(self.data)

        copy_to_clipboard(text)

        if hasattr(self.app, "notify"):
            self.app.notify("JSON copied to clipboard!", severity="success")

import subprocess
import platform
import shutil

def copy_to_clipboard(text: str) -> bool:
    system = platform.system()

    try:
        if system == "Darwin":
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            p.communicate(text.encode("utf-8"))
            return True

        if system == "Windows":
            p = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
            p.communicate(text.encode("utf-8"))
            return True

        if system == "Linux":
            if shutil.which("wl-copy"):
                p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
                p.communicate(text.encode("utf-8"))
                return True
            if shutil.which("xclip"):
                p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
                p.communicate(text.encode("utf-8"))
                return True

    except Exception:
        return False

    return False

