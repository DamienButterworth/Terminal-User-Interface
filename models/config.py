from dataclasses import dataclass

from models.github_config import GithubConfig
from models.local_config import LocalConfig


@dataclass
class Config:
    github: GithubConfig
    local: LocalConfig