"""Create the local OntiCards configuration on a fresh installation."""

import argparse
import base64
import os
from pathlib import Path
import secrets
import shlex
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from OntiCards_Api.connect_info_key import connect_info_key

SIGNING_FILES = {
    "SECRET_KEY": "onticards_jwt_signing_key",
    "SSO_SECRET_KEY": "onticards_sso_verification_key",
}


def initialize(directory, *, signing_files=False):
    target = directory / ".env"
    if target.exists() or target.is_symlink():
        return False

    values = {
        "SECRET_KEY": secrets.token_hex(32),
        "SSO_SECRET_KEY": secrets.token_hex(32),
        "CONNECT_INFO_MASTER_KEY": base64.b64encode(secrets.token_bytes(32)).decode("ascii"),
    }
    if signing_files:
        secret_dir = directory / ".secrets"
        secret_dir.mkdir(mode=0o700, exist_ok=True)
        if secret_dir.is_symlink():
            raise OSError("Secret directory cannot be a symbolic link.")
        if os.name == "posix" and secret_dir.stat().st_mode & 0o077:
            raise OSError("Secret directory must be private.")
        for key, filename in SIGNING_FILES.items():
            destination = secret_dir / filename
            if destination.is_symlink():
                raise OSError("Signing file cannot be a symbolic link.")
            if not destination.exists():
                publish_new(destination, (values[key] + "\n").encode(), ".key.")
            values[key] = ""
    lines = []
    emitted = set()
    for line in (directory / ".env.prod").read_text(encoding="utf-8-sig").splitlines():
        key = line.partition("=")[0].strip()
        if key not in values:
            lines.append(line)
        elif key not in emitted:
            lines.append(f"{key}={values[key]}")
            emitted.add(key)
    lines.extend(f"{key}={value}" for key, value in values.items() if key not in emitted)
    data = ("\n".join(lines) + "\n").encode("utf-8")

    return publish_new(target, data, ".env.")


def publish_new(target, data, prefix):
    descriptor, temp_name = tempfile.mkstemp(prefix=prefix, dir=target.parent)
    staging = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            # A same-directory hard link publishes the complete file without replacing a winner.
            os.link(staging, target)
        except FileExistsError:
            return False
        return True
    finally:
        staging.unlink()


def existing_config_warnings(target, *, signing_files=False):
    keys = {*SIGNING_FILES, "CONNECT_INFO_MASTER_KEY"}
    values = {}
    try:
        if not target.is_file():
            return ["Existing configuration is not a readable file."]
        with target.open(encoding="utf-8-sig") as stream:
            text = stream.read(1024 * 1024 + 1)
        if len(text) > 1024 * 1024:
            return ["Existing configuration is too large for this preflight."]
        for line in text.splitlines():
            key, delimiter, value = line.lstrip().removeprefix("export ").partition("=")
            key = key.strip()
            if delimiter and key in keys:
                values[key] = " ".join(shlex.split(value, comments=True))
    except (OSError, ValueError):
        return ["Existing configuration could not be parsed. Review it manually."]

    warnings = []
    if signing_files:
        for key, filename in SIGNING_FILES.items():
            if not (target.parent / ".secrets" / filename).is_file():
                warnings.append(f"Provision the Compose secret file for {key} before startup.")
    for key in sorted(keys):
        value = values.get(key, "")
        if signing_files and key in SIGNING_FILES:
            if value:
                warnings.append(f"Compose reads {key} from its secret file. The legacy inline value was preserved.")
        elif not value.strip():
            warnings.append(f"{key} is missing or empty in the local file.")
        elif "${" in value:
            warnings.append(f"{key} contains interpolation. Check its effective value before startup.")
        elif key == "SECRET_KEY" and (len(value) != 64 or not all(c in "0123456789abcdefABCDEF" for c in value)):
            warnings.append("SECRET_KEY must be 64 hexadecimal characters generated from 32 random bytes.")
        elif key == "SSO_SECRET_KEY" and len(value.strip()) < 32:
            warnings.append("SSO_SECRET_KEY has fewer than 32 non-padding characters.")
        elif key == "CONNECT_INFO_MASTER_KEY":
            try:
                connect_info_key(value)
            except ValueError as error:
                warnings.append(str(error))
    return warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-only", action="store_true", help="initialize OntiCards_Api/.env")
    args = parser.parse_args()
    directory = ROOT / "OntiCards_Api" if args.api_only else ROOT
    label = "OntiCards_Api/.env" if args.api_only else ".env"
    try:
        created = initialize(directory, signing_files=not args.api_only)
    except OSError:
        print(f"Could not complete {label}. Check directory access, free space and hard-link support.", file=sys.stderr)
        return 1
    if created:
        print(f"Created {label} with local secrets.")
    else:
        print(f"Keeping the existing {label}.")
        for warning in existing_config_warnings(directory / ".env", signing_files=not args.api_only):
            print("Warning: " + warning, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
