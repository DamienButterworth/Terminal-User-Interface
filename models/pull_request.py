from dataclasses import dataclass

@dataclass
class PullRequest:
    url: str
    updated_at: str
    author: str