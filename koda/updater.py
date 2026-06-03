import httpx

from koda import __version__

GITHUB_REPO = "SnapD3v/koda"
_API_URL    = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


async def check_update() -> str | None:
    """
    Returns the latest release tag if it differs from the current version,
    or None if already up-to-date or if the check fails.
    """
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                _API_URL,
                headers={"Accept": "application/vnd.github+json"},
                follow_redirects=True,
            )
        if r.status_code != 200:
            return None
        tag = r.json().get("tag_name", "")
        if tag and tag.lstrip("v") != __version__:
            return tag
    except Exception:
        pass
    return None
