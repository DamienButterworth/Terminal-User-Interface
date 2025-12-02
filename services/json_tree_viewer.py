import json
from dataclasses import asdict, is_dataclass

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Input, Label, Tree


def jsonify(data):
    if is_dataclass(data):
        return asdict(data)

    if hasattr(data, "model_dump"):
        return data.model_dump()

    if hasattr(data, "dict"):
        return data.dict()

    if hasattr(data, "data") and not isinstance(data, (dict, list)):
        return jsonify(data.data)

    return data


def fmt(value) -> Text:
    if isinstance(value, str):
        return Text(f'"{value}"', style="green")
    if isinstance(value, (int, float)):
        return Text(str(value), style="magenta")
    if isinstance(value, bool):
        return Text(str(value).lower(), style="yellow")
    if value is None:
        return Text("null", style="dim")
    return Text(repr(value), style="white")


def match_any(value, query: str) -> bool:
    q = query.lower()
    if isinstance(value, (dict, list)):
        try:
            text = json.dumps(value)
        except Exception:
            text = str(value)
        return q in text.lower()
    return q in str(value).lower()

class JsonTreeViewer(Container):

    def __init__(
        self,
        data,
        title="JSON Viewer",
        label_key=None,
        label_keys: dict | None = None,
        expand_all=False,
        pre_label_key="",
        post_label_key="",
    ):
        super().__init__()

        self._original_data = jsonify(data)
        self._title = title

        self._label_key = label_key

        self._label_keys = label_keys or {}

        self._expand_all = expand_all
        self._pre_label_key = pre_label_key
        self._post_label_key = post_label_key

    def compose(self) -> ComposeResult:
        yield Label(self._title, classes="section")
        yield Input(placeholder="Search JSON…", id="json_search")
        yield Tree("", id="json_tree")

    async def on_mount(self) -> None:
        self.call_later(self._populate_tree)

    def _populate_tree(self):
        tree = self.query_one("#json_tree", Tree)
        tree.show_root = False
        root = tree.root

        root.remove_children()

        data = self._original_data

        if isinstance(data, list):
            self._build_value(root, data, parent_key=None)
        else:
            self._build_tree(root, data)

        root.expand()

        if self._expand_all:
            root.expand_all()

    def _build_tree(self, node, data):

        if isinstance(data, dict):
            for key, value in data.items():
                child = node.add(str(key))
                self._build_value(child, value, parent_key=key)
            return

        if isinstance(data, list):
            raise RuntimeError("List passed directly to _build_tree; use _build_value.")

        node.set_label(fmt(data))

    def _build_value(self, node, value, parent_key=None):

        if isinstance(value, list):

            if parent_key in self._label_keys:
                list_label_key = self._label_keys[parent_key]
            else:
                list_label_key = self._label_key

            for index, item in enumerate(value):

                if isinstance(item, dict) and list_label_key and list_label_key in item:
                    label = (
                        self._pre_label_key +
                        str(item[list_label_key]) +
                        self._post_label_key
                    )
                else:
                    label = f"[{index}]"

                child = node.add(label)
                self._build_value(child, item, parent_key=None)

            return

        if isinstance(value, dict):
            for key, child_value in value.items():
                child = node.add(str(key))
                self._build_value(child, child_value, parent_key=key)
            return

        node.add(fmt(value))

    def on_input_changed(self, event: Input.Changed):
        if event.input.id != "json_search":
            return

        query = event.value.strip().lower()

        tree = self.query_one("#json_tree", Tree)
        root = tree.root
        root.remove_children()

        if not query:
            self._build_tree(root, self._original_data)
        else:
            filtered = self._filter_json(self._original_data, query)
            self._build_tree(root, filtered)

        root.expand_all()

    def _filter_json(self, data, query: str):

        q = query.lower()

        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                key_match = q in str(key).lower()
                value_match = match_any(value, q)

                filtered_value = self._filter_json(value, q)

                if key_match or value_match:
                    if isinstance(filtered_value, (dict, list)):
                        result[key] = filtered_value
                    else:
                        result[key] = value
            return result

        if isinstance(data, list):
            result_list = []
            for item in data:
                value_match = match_any(item, q)
                filtered_item = self._filter_json(item, q)

                if value_match:
                    if isinstance(filtered_item, (dict, list)):
                        result_list.append(filtered_item)
                    else:
                        result_list.append(item)
            return result_list

        return data
