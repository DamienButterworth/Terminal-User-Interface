from .client import GitHubClient
import os
from git import Repo

class LocalGithubRequests:
    def __init__(self, organisation: str):
        self.client = GitHubClient()
        self.organisation = organisation

    def clone_repo(self, repo: str, dest_dir: str, branch: str = None):
        repo_dir = os.path.join(dest_dir, repo)
        if os.path.exists(repo_dir):
            raise FileExistsError(f"Destination already exists: {repo_dir}")

        url = f"git@github.com:{self.organisation}/{repo}.git"

        print(f"Cloning {url} into {repo_dir}...")

        repo = Repo.clone_from(url, repo_dir)

        if branch:
            repo.git.checkout(branch)

        return repo_dir