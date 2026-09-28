"""Build SSO callback redirects without putting the session token in a query."""

from urllib.parse import quote, urlsplit, urlunsplit


def is_allowed_redirect(redirect_url, allowed_origins):
    """Accept local paths and absolute URLs whose origin is explicitly allowed."""
    parts = urlsplit(redirect_url)
    if not parts.scheme and not parts.netloc:
        return redirect_url.startswith("/") and not redirect_url.startswith("//")

    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return False

    requested_origin = f"{parts.scheme.lower()}://{parts.netloc.lower()}"
    normalized_allowed = set()
    for value in allowed_origins:
        origin = urlsplit(value.strip())
        if origin.scheme and origin.netloc:
            normalized_allowed.add(f"{origin.scheme.lower()}://{origin.netloc.lower()}")
    return requested_origin in normalized_allowed


def with_access_token_fragment(redirect_url, access_token):
    """Append an encoded access token to the URL fragment."""
    parts = urlsplit(redirect_url)
    token_parameter = "access_token=" + quote(access_token, safe="")
    fragment = f"{parts.fragment}&{token_parameter}" if parts.fragment else token_parameter
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, fragment))
