import yaml
from pathlib import Path
from typing import Union

from models.config import Config
from models.github_config import GithubConfig
from models.local_config import LocalConfig


class YAMLConfig:
    BASE_DIR = Path(__file__).resolve().parent
    DEFAULT_PATH = Path(BASE_DIR / "../config.yaml")

    def __get_github_config(self) -> "GithubConfig":
        github_data = self.get("github", {})

        return GithubConfig(
            active_team_members=github_data.get("active-team-members", []),
            organisation=github_data.get("organisation", ""),
            team=github_data.get("team", ""),
            ignored_repositories=github_data.get("ignored-repositories", []),
        )

    def __get_local_config(self) -> "LocalConfig":
        local_data = self.get("local", {})
        return LocalConfig(active_working_directory=local_data.get("active-working-directory", ""))

    def __init__(self, path: Union[str, Path] = None):
        self.path = Path(path) if path else self.DEFAULT_PATH
        self._data = None
        self.load()
        self.config = Config(self.__get_github_config(), self.__get_local_config())

    def load(self):
        if not self.path.exists():
            raise FileNotFoundError(f"Config file not found: {self.path}")

        with open(self.path, "r") as f:
            self._data = yaml.safe_load(f) or {}

    def save(self, config: dict):
        with self.path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(
                config,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

    def reload(self):
        self.load()

    def get(self, key, default=None):
        return self._data.get(key, default)

    def get_nested(self, path, default=None):
        parts = path.split(".")
        value = self._data
        for p in parts:
            if not isinstance(value, dict):
                return default
            value = value.get(p, default)
        return value

    @property
    def data(self):
        return self._data
