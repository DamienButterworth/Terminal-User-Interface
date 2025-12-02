from textual.app import App, ComposeResult
from textual.containers import Vertical, Container
from textual.widgets import Button

from content.github import GithubContent
from content.local import LocalContent
from content.settings import SettingsContent

from config import YAMLConfig
from content import HomeContent


class MainContent(Container):
    def clear_and_mount(self, *widgets):
        self.remove_children()
        for w in widgets:
            self.mount(w)


class SidebarApp(App):
    CSS_PATH = "./content/styles.css"

    def compose(self) -> ComposeResult:
        with Vertical(id="sidebar"):
            yield Button("Home", id="home")
            yield Button("GitHub", id="github")
            yield Button("Local", id="local")
            yield Button("Settings", id="settings")
        yield MainContent(HomeContent(), id="content")

    def show_in_content(self, *widgets):
        self.query_one(MainContent).clear_and_mount(*widgets)

    def on_button_pressed(self, event: Button.Pressed):
        match event.button.id:
            case "home":
                self.show_in_content(HomeContent())
            case "github":
                self.show_in_content(GithubContent())
            case "settings":
                config = YAMLConfig()
                self.show_in_content(SettingsContent(config))
            case "local":
                self.show_in_content(LocalContent())


if __name__ == "__main__":
    SidebarApp().run()
