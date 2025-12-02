from .client import GitHubClient

class GitHubTeamRequests:
    def __init__(self, organisation: str, team_slug: str):
        self.client = GitHubClient()
        self.organisation = organisation
        self.team_slug = team_slug

    def list_teams(self):
        return self.client.get(f"/orgs/{self.organisation}/teams")

    def get_team_members(self):
        return self.client.get(f"/orgs/{self.organisation}/teams/{self.team_slug}/members")

    def get_team_repos(self):
        return self.client.get(f"/orgs/{self.organisation}/teams/{self.team_slug}/repos")

    def add_team_member(self, username: str, role="member"):
        data = {"role": role}
        return self.client.put(f"/orgs/{self.organisation}/teams/{self.team_slug}/memberships/{username}", data)

    def remove_team_member(self, username: str):
        return self.client.delete(
            f"/orgs/{self.organisation}/teams/{self.team_slug}/memberships/{username}"
        )
