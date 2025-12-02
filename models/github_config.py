from typing import List
from dataclasses import dataclass

@dataclass
class GithubConfig:
    active_team_members: List[str]
    organisation: str
    team: str
    ignored_repositories: List[str]