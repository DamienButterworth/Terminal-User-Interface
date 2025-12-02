from typing import Protocol, Any

class ContentRouter(Protocol):
    def show_in_content(self, *widgets: Any) -> None:
        ...
