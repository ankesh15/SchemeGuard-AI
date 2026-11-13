"""Verify the local production profile over an explicitly trusted test TLS certificate."""

import argparse
import http.cookiejar
import json
import re
import secrets
import ssl
import urllib.error
import urllib.request
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--certificate", required=True)
    args = parser.parse_args()
    origin = "https://localhost:13443"
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=args.certificate)),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    )
    csrf = None

    def request(path, body=None, method="GET", expected=200):
        headers = {"Origin": origin, "Content-Type": "application/json"}
        if csrf:
            headers["X-CSRF-Token"] = csrf
        try:
            response = opener.open(
                urllib.request.Request(
                    origin + path,
                    data=json.dumps(body).encode() if body is not None else None,
                    headers=headers,
                    method=method,
                ),
                timeout=60,
            )
        except urllib.error.HTTPError as error:
            if error.code == expected:
                return None
            raise
        assert response.status == expected
        return response

    home = request("/")
    html = home.read().decode()
    csp = home.headers.get("Content-Security-Policy", "")
    assert "strict-dynamic" in csp and "object-src 'none'" in csp
    nonce = re.search(r"'nonce-([^']+)'", csp).group(1)
    scripts = re.findall(r"<script\b[^>]*>", html)
    assert scripts and all(f'nonce="{nonce}"' in script for script in scripts), (
        "Every rendered script must have the response nonce"
    )
    assert home.headers.get("Strict-Transport-Security")
    username = "prod_verification_" + uuid4().hex[:10]
    password = secrets.token_urlsafe(32)
    response = request(
        "/api/account/auth/register", {"username": username, "password": password}, "POST", 201
    )
    cookie = response.headers.get("Set-Cookie", "")
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie
    account = json.load(response)
    csrf = account["csrf_token"]
    assert json.load(request("/api/account/me"))["role"] == "citizen"
    assert json.load(request("/api/account/profiles/me", {"age_years": 21, "state": "Assam"}, "PUT"))[
        "exists"
    ]
    assert request("/api/admin/documents", expected=403) is None
    # Only this newly created synthetic verification account is removed.
    request("/api/account/me", {"current_password": password, "acknowledge_deletion": True}, "DELETE", 204)
    request("/api/account/me", expected=401)
    print(
        json.dumps(
            {
                "result": "PASS",
                "scope": "local production-profile images behind loopback TLS verification harness",
                "nonce_CSP": "all rendered scripts match a fresh response nonce",
                "cookies": "Secure, HttpOnly, SameSite=Strict",
                "auth_profile_isolation_deletion": "PASS",
                "cloud_deployment": False,
                "object_storage": "filesystem explicitly opted in for local test; real S3 not exercised",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
