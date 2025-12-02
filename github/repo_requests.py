from .client import GitHubClient

class GitHubRepoRequests:
    def __init__(self, organisation: str, repo: str):
        self.client = GitHubClient()
        self.repo = repo
        self.organisation = organisation

    def get_repo(self):
        return self.client.get(f"/repos/{self.client}/{self.repo}")

    def list_pull_requests(self, state: str = "open"):
        return self.client.get(
            f"/repos/{self.organisation}/{self.repo}/pulls", params={"state": state}
        )

    def get_pull_request(self, pr_number: int):
        return self.client.get(
            f"/repos/{self.organisation}/{self.repo}/pulls/{pr_number}"
        )

    def list_issues(self, state: str = "open"):
        return self.client.get(
            f"/repos/{self.organisation}/{self.repo}/issues", params={"state": state}
        )

    def get_issue(self, issue_number: int):
        return self.client.get(
            f"/repos/{self.organisation}/{self.repo}/issues/{issue_number}"
        )

    def list_commits(self):
        return self.client.get(
            f"/repos/{self.organisation}/{self.repo}/commits"
        )

    def get_commit(self, sha: str):
        return self.client.get(
            f"/repos/{self.organisation}/{self.repo}/commits/{sha}"
        )

    def list_branches(self):
        return self.client.get(
            f"/repos/{self.organisation}/{self.repo}/branches"
        )

    def get_branch(self, branch: str):
        return self.client.get(
            f"/repos/{self.organisation}/{self.repo}/branches/{branch}"
        )

    def list_collaborators(self):
        return self.client.get(
            f"/repos/{self.organisation}/{self.repo}/collaborators"
        )

    def add_collaborator(self, username: str, permission: str = "push"):
        data = {"permission": permission}
        return self.client.put(
            f"/repos/{self.organisation}/{self.repo}/collaborators/{username}", data
        )

    def remove_collaborator(self, username: str):
        return self.client.delete(
            f"/repos/{self.organisation}/{self.repo}/collaborators/{username}"
        )


if __name__ == "__main__":
    r = GitHubRepoRequests("hmrc", "app-config-qa")
    print(r.list_pull_requests().head().pretty_print_json())
