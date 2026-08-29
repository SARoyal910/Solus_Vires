"""Generates a VAPID keypair for Web Push and a CHECKIN_TOKEN_SECRET.

Run once and paste the output into .env:

    python backend/scripts/generate_vapid_keys.py

The public key is safe to expose to browsers (it's served from
/api/checkin/vapid-public-key). The private key and token secret are
regular secrets - keep them out of version control, same as the rest of
this project's .env values.
"""
import secrets

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid
from py_vapid.utils import b64urlencode


def main() -> None:
    vapid = Vapid()
    vapid.generate_keys()

    private_raw = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
    public_raw = vapid.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )

    print("VAPID_PRIVATE_KEY=" + b64urlencode(private_raw))
    print("VAPID_PUBLIC_KEY=" + b64urlencode(public_raw))
    print("CHECKIN_TOKEN_SECRET=" + secrets.token_urlsafe(32))


if __name__ == "__main__":
    main()
