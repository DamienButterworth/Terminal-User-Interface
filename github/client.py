import requests
import json
import os


def _handle_response(response):
    if 200 <= response.status_code < 300:
        try:
            return response.json()
        except ValueError:
            return response.text
    else:
        raise Exception(f"GitHub API Error {response.status_code}: {response.text}")


def _get_nested(item, path):
    keys = path.split(".")
    value = item
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k)
        else:
            return None
    return value


class GitHubResponse:
    def __init__(self, data):
        self.data = data

    def getFields(self, fields):
        if isinstance(self.data, list):
            result = []
            for item in self.data:
                if isinstance(item, dict):
                    extracted = {
                        field: _get_nested(item, field)
                        for field in fields
                    }
                    result.append(extracted)
            return GitHubResponse(result)

        if isinstance(self.data, dict):
            extracted = {
                field: _get_nested(self.data, field)
                for field in fields
            }
            return GitHubResponse(extracted)

        return GitHubResponse(None)

    def pluck(self, field: str):
        if isinstance(self.data, list):
            return GitHubResponse([item.get(field) for item in self.data if isinstance(item, dict)])
        return GitHubResponse(None)

    def filter(self, predicate):
        if isinstance(self.data, list):
            return GitHubResponse([item for item in self.data if predicate(item)])
        return GitHubResponse(None)

    def filter_not(self, predicate):
        if isinstance(self.data, list):
            return GitHubResponse([item for item in self.data if not predicate(item)])
        return GitHubResponse(None)

    def head(self):
        if isinstance(self.data, list) and self.data:
            return GitHubResponse(self.data[0])
        return GitHubResponse(None)

    def last(self):
        if isinstance(self.data, list) and self.data:
            return GitHubResponse(self.data[len(self.data) - 1])
        return GitHubResponse(None)

    def take(self, n: int):
        if isinstance(self.data, list) and self.data:
            return GitHubResponse(self.data[n])
        return GitHubResponse(None)

    def pretty_print_json(self):
        return json.dumps(self.data, indent=2)

    def value(self):
        return self.data

    def __repr__(self):
        return repr(self.data)


class GitHubClient:
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        self.base_url = "https://api.github.com"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json"
        })

    def get(self, endpoint: str, params=None):
        url = f"{self.base_url}{endpoint}"
        results = []

        while url:
            response = self.session.get(url, params=params)
            data = _handle_response(response)

            if isinstance(data, list):
                results.extend(data)
            else:
                return GitHubResponse(data)

            link = response.headers.get("Link", "")
            next_url = None
            for part in link.split(","):
                if 'rel="next"' in part:
                    next_url = part[part.find("<") + 1:part.find(">")]
            url = next_url
            params = None

        return GitHubResponse(results)

    def post(self, endpoint: str, data=None):
        url = f"{self.base_url}{endpoint}"
        response = self.session.post(url, json=data)
        return GitHubResponse(_handle_response(response))

    def patch(self, endpoint: str, data=None):
        url = f"{self.base_url}{endpoint}"
        response = self.session.patch(url, json=data)
        return GitHubResponse(_handle_response(response))

    def put(self, endpoint: str, data=None):
        url = f"{self.base_url}{endpoint}"
        response = self.session.put(url, json=data)
        return GitHubResponse(_handle_response(response))

    def delete(self, endpoint: str):
        url = f"{self.base_url}{endpoint}"
        response = self.session.delete(url)
        if response.status_code in (204, 200):
            return True
        return GitHubResponse(_handle_response(response))
