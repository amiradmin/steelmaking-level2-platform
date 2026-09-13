#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

EXPECTED_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAHFpgcga1SAUY+ShwCQjngxsuBFLAJUuqmoJLUqhB4B4=
-----END PUBLIC KEY-----
"""


def b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def main() -> None:
    parser = argparse.ArgumentParser(description="Issue a signed Steelmaking Level 2 license token.")
    parser.add_argument("--private-key", required=True, help="Path to the vendor Ed25519 private PEM key")
    parser.add_argument("--customer", required=True)
    parser.add_argument("--license-id", required=True)
    parser.add_argument("--expires-at", required=True, help="ISO-8601 date/time, e.g. 2026-10-13T23:59:59+03:30")
    parser.add_argument("--grace-days", type=int, default=7)
    parser.add_argument("--product", default="Steelmaking Level 2")
    args = parser.parse_args()

    key_data = Path(args.private_key).expanduser().read_bytes()
    loaded = serialization.load_pem_private_key(key_data, password=None)
    if not isinstance(loaded, Ed25519PrivateKey):
        raise SystemExit("Private key must be an Ed25519 PEM key.")

    public_pem = loaded.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    if public_pem != EXPECTED_PUBLIC_KEY_PEM:
        raise SystemExit("This private key does not match the public key embedded in the project.")

    payload = {
        "customer": args.customer,
        "expires_at": args.expires_at,
        "grace_days": max(0, args.grace_days),
        "license_id": args.license_id,
        "product": args.product,
    }
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = loaded.sign(payload_bytes)
    token = f"{b64url(payload_bytes)}.{b64url(signature)}"

    print("LICENSE_TOKEN=" + token)


if __name__ == "__main__":
    main()
