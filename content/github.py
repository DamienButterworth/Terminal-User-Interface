import asyncio
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from textual import on, work
from textual.containers import VerticalScroll
from textual.widgets import Button

from config import YAMLConfig
from github import LocalGithubRequests, GitHubRepoRequests
from github.team_requests import GitHubTeamRequests
from .json_render import JsonRender

from textual_fspicker import SelectDirectory


if TYPE_CHECKING:
    pass

class GithubContent(VerticalScroll):

    def __init__(self):
        super().__init__()
        self.github_config = YAMLConfig().config.github
        self.gtr = GitHubTeamRequests(self.github_config.organisation, self.github_config.team)
        self.lgr = LocalGithubRequests(self.github_config.organisation)

    @property
    def app(self) -> "ContentRouter":
        return super().app

    def compose(self):
        yield Button("Organisation Teams", id="org_teams")
        yield Button("Team Repositories", id="team_repos")
        yield Button("Team Members", id="team_members")
        yield Button("Team Pull Requests", id="team_pull_requests")
        yield Button("List Team Branches", id="team_branches")
        yield Button("Clone Team Repositories", id="clone_team_repos")
        yield Button("Update local repositories", id="update_local_repos")

    async def notify_and_run(self, message, func, *args, **kwargs):
        self.app.notify(message, timeout=2)
        return await asyncio.to_thread(func, *args, **kwargs)

    def update_single_repo(self, repo_path: Path):
        def run(*args):
            return subprocess.run(
                ["git", *args],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )

        results = {
            "stash": run("stash", "-u"),
            "checkout": run("checkout", "main"),
            "pull": run("pull"),
        }

        return repo_path.name, results

    async def update_all_repos(self, directory: str):
        root_path = Path(directory)

        repos = [
            p for p in root_path.iterdir()
            if p.is_dir() and (p / ".git").exists()
        ]

        if not repos:
            self.app.notify("No Git repositories found.", severity="warning")
            return

        self.app.notify(f"Updating {len(repos)} repositories…", severity="information")

        async def update_one(repo_path):
            repo_name = repo_path.name
            self.app.notify(f"Updating {repo_name}…", timeout=2)

            name, results = await asyncio.to_thread(self.update_single_repo, repo_path)

            # Check success
            pull_ok = results["pull"].returncode == 0

            if pull_ok:
                self.app.notify(f"✓ {repo_name} updated successfully", severity="information", timeout=2)
            else:
                self.app.notify(
                    f"⚠ {repo_name} update had issues:\n{results['pull'].stderr}",
                    severity="warning",
                    timeout=4,
                )

            return pull_ok

        results = await asyncio.gather(*(update_one(repo) for repo in repos))

        success = sum(1 for r in results if r)
        failed = len(repos) - success

        self.app.notify(
            f"Update complete: {success} OK, {failed} failed.",
            severity="information" if failed == 0 else "warning",
            timeout=4
        )

    async def clone_team_repos_parallel(self, directory):
        repos = await self.__get_team_repo_names()

        semaphore = asyncio.Semaphore(4)

        async def clone_one(repo, index):
            async with semaphore:
                self.app.notify(
                    f"Cloning {repo}... ({index}/{len(repos)})",

                    severity="information",
                    timeout=2
                )
                await asyncio.to_thread(self.lgr.clone_repo, repo, directory, "main")

        tasks = [
            clone_one(repo, i)
            for i, repo in enumerate(repos, start=1)
        ]

        await asyncio.gather(*tasks)
        self.app.notify(
            f"Cloning completed ({len(repos)} repositories).",
            severity="information",
            timeout=3
        )

    async def __get_team_repo_names(self):

        team_repo_ghr = await self.notify_and_run(
            f"Retrieving repositories for team: {self.github_config.team}",
            self.gtr.get_team_repos
        )

        repo_names = [repo["name"] for repo in team_repo_ghr.data]

        if not repo_names:
            self.app.notify("No repositories found.", severity="warning")
            return []
        else:
            return repo_names

    @on(Button.Pressed)
    @work
    async def on_button_pressed(self, event: Button.Pressed):
        match event.button.id:
            case "org_teams":
                result = await self.notify_and_run(f"Retrieving teams for organisation: {self.github_config.organisation}", self.gtr.list_teams)
                self.app.show_in_content(JsonRender(result, "org_team", {None: "name"}))
            case "team_repos":
                result = await self.notify_and_run(f"Retrieving repositories for team: {self.github_config.team}", self.gtr.get_team_repos)
                self.app.show_in_content(JsonRender(result, "team_repos", {None: "name"}))
            case "team_members":
                result = await self.notify_and_run(f"Retrieving team members for {self.github_config.team}", self.gtr.get_team_members)
                self.app.show_in_content(JsonRender(result, "team_members", {None: "login"}))
            case "team_branches":
                repo_names = await self.__get_team_repo_names()
                data = []
                for repo in repo_names:
                    grr = GitHubRepoRequests(self.github_config.organisation, repo)
                    result = await self.notify_and_run(f"Retrieving active/stale branches for repository: {repo}", grr.list_branches)
                    modified = {
                        "repository": repo,
                        "branches": result.data
                    }
                    data.append(modified)

                self.app.show_in_content(JsonRender(data, "team_branches", {None: "repository", "branches": "name"}))
            case "team_pull_requests":
                repo_names = await self.__get_team_repo_names()
                data = []
                for repo in repo_names:
                    grr = GitHubRepoRequests(self.github_config.organisation, repo)
                    result = await self.notify_and_run(
                        f"Retrieving pull requests for repository: {repo}",
                        grr.list_pull_requests
                    )

                    if not result.data:
                        continue

                    modified = {
                        "repository": repo,
                        "pull requests": result.data
                    }
                    data.append(modified)
                self.app.show_in_content(JsonRender(data, "team_pull_requests", {None: "repository", "pull requests": "title"}))
            case "clone_team_repos":
                directory = await (self.app.push_screen_wait(SelectDirectory()))
                if directory:
                    await self.clone_team_repos_parallel(directory)
                else:
                    self.app.notify("No directory selected")
            case "update_local_repos":
                directory = await (self.app.push_screen_wait(SelectDirectory()))
                if directory:
                    await self.update_all_repos(directory)
                else:
                    self.app.notify("No directory selected")
