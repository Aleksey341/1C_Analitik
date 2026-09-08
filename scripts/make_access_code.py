"""Generate a user access code and its SHA-256 hash for the managed gateway."""
from __future__ import annotations

import hashlib
import secrets


def main() -> int:
    code = "1CA-" + secrets.token_urlsafe(18)
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
    print("ACCESS_CODE=" + code)
    print("SHA256=" + digest)
    print()
    print("Give ACCESS_CODE to the user.")
    print("Store only SHA256 in MANAGED_ACCESS_CODE_HASHES on the server.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
