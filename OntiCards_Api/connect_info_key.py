"""Validate the persistent data-source encryption key without exposing its value."""

import base64
import binascii
import hashlib


_PUBLIC_TEMPLATE_VALUES = {
    "onticards-dev-connect-key",
    "your-32-byte-base64-encoded-key-here",
}


def connect_info_key(value):
    if not value or not value.strip():
        raise ValueError("CONNECT_INFO_MASTER_KEY is required. Configure the existing or newly provisioned persistent key.")
    if value.strip() in _PUBLIC_TEMPLATE_VALUES:
        raise ValueError("CONNECT_INFO_MASTER_KEY uses a public template value. Follow the migration guide for existing data.")
    if len(value.strip()) < 16 or len(set(value.strip())) < 8:
        raise ValueError("CONNECT_INFO_MASTER_KEY is too weak. Follow the migration guide for existing data.")

    # Keep the existing derivation for valid historical configurations.
    # Do not trim or reinterpret an existing key when decrypting stored data.
    try:
        key = base64.b64decode(value)[:32]
    except (binascii.Error, ValueError):
        key = hashlib.sha256(value.encode()).digest()
    if len(key) not in (16, 24, 32) or len(set(key)) < 8:
        raise ValueError("CONNECT_INFO_MASTER_KEY does not yield a valid encryption key.")
    return key
