import os
import subprocess
import tempfile
from urllib.parse import quote, urlsplit, urlunsplit

import requests


GITEE_API = "https://gitee.com/api/v5"
GITHUB_API = "https://api.github.com"
TIMEOUT = 30


def get_json(url, *, headers=None, params=None):
    try:
        response = requests.get(
            url, headers=headers, params=params, timeout=TIMEOUT
        )
    except requests.RequestException:
        raise RuntimeError("API request failed") from None

    if not response.ok:
        raise RuntimeError(f"API request failed with HTTP {response.status_code}")

    try:
        return response.json()
    except requests.exceptions.JSONDecodeError:
        raise RuntimeError("API returned invalid JSON") from None


def get_repositories(url, *, headers=None, params=None):
    repositories = []
    page = 1

    while True:
        page_params = {**(params or {}), "page": page, "per_page": 100}
        result = get_json(url, headers=headers, params=page_params)
        if not isinstance(result, list):
            raise RuntimeError("API returned an unexpected repository list")
        if not result:
            return repositories
        repositories.extend(result)
        page += 1


def authenticated_url(url, username, token):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise RuntimeError("Repository URL must use HTTPS")
    netloc = f"{quote(username, safe='')}:{quote(token, safe='')}@{parsed.netloc}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def run_git(*arguments):
    result = subprocess.run(
        ["git", *arguments], capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise RuntimeError(f"Git command failed with exit code {result.returncode}")


def main():
    gitee_token = os.environ.get("GITEE_TOKEN")
    github_token = os.environ.get("GH_TOKEN")
    gitee_user = os.environ.get("GITEE_USER")
    if not all((gitee_token, github_token, gitee_user)):
        raise RuntimeError("GITEE_TOKEN, GH_TOKEN and GITEE_USER must be configured")

    github_headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    github_user = get_json(f"{GITHUB_API}/user", headers=github_headers)
    github_owner = github_user.get("login")
    if not github_owner:
        raise RuntimeError("Could not determine the GitHub account name")

    gitee_repositories = get_repositories(
        f"{GITEE_API}/user/repos",
        params={"access_token": gitee_token},
    )
    github_repositories = get_repositories(
        f"{GITHUB_API}/user/repos",
        headers=github_headers,
        params={"type": "owner", "sort": "full_name"},
    )
    github_names = {repo["name"].casefold() for repo in github_repositories}

    for repository in gitee_repositories:
        name = repository.get("name") or repository.get("path")
        clone_url = repository.get("clone_url")
        if not name:
            print("[!] Skipping a Gitee repository without a name")
            continue
        if not clone_url:
            full_name = repository.get("full_name") or ""
            if "/" in full_name:
                namespace, repository_path = full_name.rsplit("/", 1)
            else:
                owner = repository.get("owner") or {}
                namespace = owner.get("login") or gitee_user
                repository_path = repository.get("path") or name
            clone_path = "/".join(
                quote(part, safe="") for part in (namespace, repository_path)
            )
            clone_url = f"https://gitee.com/{clone_path}.git"
            print(f"[!] {name} has no clone_url; using its canonical Gitee URL")

        if name.casefold() not in github_names:
            payload = {
                "name": name,
                "private": bool(repository.get("private")),
                "description": repository.get("description") or "",
            }
            try:
                response = requests.post(
                    f"{GITHUB_API}/user/repos",
                    json=payload,
                    headers=github_headers,
                    timeout=TIMEOUT,
                )
            except requests.RequestException:
                print(f"[!] Could not create GitHub repository {name}: request failed")
                continue
            if response.status_code != 201:
                print(
                    f"[!] Could not create GitHub repository {name}: "
                    f"HTTP {response.status_code}"
                )
                continue
            github_names.add(name.casefold())
            print(f"[+] Created GitHub repository {name}")

        print(f"[*] Mirroring {name}")
        source_url = authenticated_url(clone_url, gitee_user, gitee_token)
        target_url = authenticated_url(
            f"https://github.com/{github_owner}/{name}.git",
            "x-access-token",
            github_token,
        )

        try:
            with tempfile.TemporaryDirectory(prefix="gitee-sync-") as temp_dir:
                mirror_path = os.path.join(temp_dir, "repository.git")
                run_git("clone", "--mirror", source_url, mirror_path)
                run_git("-C", mirror_path, "push", "--mirror", target_url)
        except (OSError, RuntimeError) as error:
            print(f"[!] Sync failed for {name}: {error}")
            continue

        print(f"[+] Synced {name}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        raise SystemExit(str(error)) from None