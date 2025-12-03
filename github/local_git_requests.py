from .client import GitHubClient
import os
from git import Repo
import asyncio
from pathlib import Path
import subprocess

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

    def update_single_repo(self, repo_path: Path):
        def run(*args):
            return subprocess.run(
                ["git", *args],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )

        results = {}

        results["stash"] = run("stash", "-u")
        results["checkout"] = run("checkout", "main")
        results["pull"] = run("pull")

        return repo_path.name, results

    async def update_all_repos(self, root: str):
        root_path = Path(root)

        repos = [
            p for p in root_path.iterdir()
            if p.is_dir() and (p / ".git").exists()
        ]

        tasks = [
            asyncio.to_thread(self.update_single_repo, repo)
            for repo in repos
        ]

        for coro in asyncio.as_completed(tasks):
            name, results = await coro
            print(f"\n📁 {name}")

            for step, proc in results.items():
                print(f"--- {step} ---")
                print(proc.stdout or proc.stderr)


