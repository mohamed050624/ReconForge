"""ReconForge V1 constants."""

from __future__ import annotations

import re


WEB_ASSET_TYPES = {"URL", "WILDCARD"}
MOBILE_ASSET_TYPES = {"GOOGLE_PLAY_APP_ID", "APPLE_STORE_APP_ID"}

PROFILE_TOOLS: dict[str, list[str]] = {
    "light": [
        "subfinder",
        "assetfinder",
        "httpx",
    ],
    "standard": [
        "subfinder",
        "assetfinder",
        "httpx",
        "whatweb",
        "katana",
    ],
    "deep": [
        "subfinder",
        "assetfinder",
        "amass",
        "httpx",
        "whatweb",
        "katana",
        "gau",
        "waybackurls",
    ],
    "report-only": [],
}

INTERESTING_PATH_KEYWORDS = (
    "admin",
    "api",
    "auth",
    "backup",
    "config",
    "dashboard",
    "debug",
    "dev",
    "graphql",
    "internal",
    "login",
    "logout",
    "oauth",
    "panel",
    "private",
    "profile",
    "reset",
    "session",
    "settings",
    "signin",
    "signup",
    "stage",
    "staging",
    "swagger",
    "token",
    "upload",
    "user",
    "v1",
    "v2",
    "v3",
)

API_PATH_KEYWORDS = (
    "/api/",
    "/apis/",
    "/v1/",
    "/v2/",
    "/v3/",
    "/v4/",
    "/graphql",
    "/rest/",
    "/rpc/",
    "/jsonrpc",
    "/gateway/",
)

API_HOST_KEYWORDS = (
    "api.",
    "apis.",
    "graphql.",
    "gateway.",
    "developer.",
    "developers.",
)

GRAPHQL_KEYWORDS = (
    "graphql",
    "gql",
)

SWAGGER_OPENAPI_KEYWORDS = (
    "swagger",
    "openapi",
    "api-docs",
    "apidocs",
    "redoc",
)

AUTH_KEYWORDS = (
    "auth",
    "login",
    "signin",
    "sso",
    "oauth",
    "token",
    "session",
    "jwt",
    "password",
    "reset",
)

UPLOAD_KEYWORDS = (
    "upload",
    "file",
    "media",
    "avatar",
    "image",
    "attachment",
)

JS_EXTENSIONS = (
    ".js",
    ".mjs",
)

STATIC_EXTENSIONS = (
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp4",
    ".mp3",
    ".webp",
    ".avif",
)

URL_RE = re.compile(r"https?://[^\s\"'<>\\)\\]]+", re.IGNORECASE)
DOMAIN_RE = re.compile(r"^(?:[a-z0-9-]+\.)+[a-z]{2,}$", re.IGNORECASE)
