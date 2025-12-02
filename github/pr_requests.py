from .client import GitHubClient

class GitHubPullRequestActions:
    def __init__(self, owner: str, repo: str):
        self.client = GitHubClient()
        self.owner = owner
        self.repo = repo

    def list_reviews(self, pr_number: int):
        return self.client.get(
            f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}/reviews"
        )

    def create_review(self, pr_number: int, body: str, event: str = "COMMENT"):
        data = {"body": body, "event": event}
        return self.client.post(
            f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}/reviews", data
        )

    def submit_review(self, pr_number: int, review_id: int, body: str, event: str):
        data = {"body": body, "event": event}
        return self.client.post(
            f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}/reviews/{review_id}/events", data
        )

    def merge_pull_request(self, pr_number: int, commit_title: str = None, merge_method: str = "merge"):
        data = {"merge_method": merge_method}
        if commit_title:
            data["commit_title"] = commit_title
        return self.client.put(
            f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}/merge", data
        )

    def list_comments(self, pr_number: int):
        return self.client.get(
            f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}/comments"
        )

    def add_comment(self, pr_number: int, body: str):
        data = {"body": body}
        return self.client.post(
            f"/repos/{self.owner}/{self.repo}/issues/{pr_number}/comments", data
        )

    def update_pull_request(self, pr_number: int, title: str = None, body: str = None, state: str = None):
        data = {}
        if title:
            data["title"] = title
        if body:
            data["body"] = body
        if state:
            data["state"] = state
        return self.client.patch(
            f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}", data
        )

    def get_pull_request_files(self, pr_number: int):
        return self.client.get(
            f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}/files"
        )

    def approve(self, pr_number: int, body: str = "Approved"):
        return self.create_review(pr_number, body, event="APPROVE")

    def request_changes(self, pr_number: int, body: str):
        return self.create_review(pr_number, body, event="REQUEST_CHANGES")


if __name__ == "__main__":
    p = GitHubPullRequestActions("hmrc", "repo-name")
    print(p.list_reviews(123).pretty_print_json())