import json
import base64
import hashlib
import pathlib
import sys
import os
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

BASE_DIR = pathlib.Path(__file__).resolve().parent

# 容器内 license 路径：我们约定挂到这里
LICENSE_PATH = BASE_DIR / "license.dat"
PUB_KEY_PATH = BASE_DIR / "license_pub.pem"

def _load_pub_key():
    if not PUB_KEY_PATH.exists():
        print("[LICENSE] 公钥文件缺失: license_pub.pem", file=sys.stderr)
        return None
    try:
        return serialization.load_pem_public_key(PUB_KEY_PATH.read_bytes())
    except Exception as e:
        print(f"[LICENSE] 公钥加载失败: {e}", file=sys.stderr)
        return None

def _get_fingerprint():
    """
    从宿主挂载的信息生成机器指纹。
    推荐在 docker run/docker-compose 里挂：
      /etc/machine-id                   -> /host/etc/machine-id
      /sys/class/dmi/id/product_uuid    -> /host/sys/class/dmi/id/product_uuid
    或使用环境变量 LICENSE_FINGERPRINT 作为兜底。
    """
    candidates = [
        "/host/etc/machine-id",
        "/host/sys/class/dmi/id/product_uuid",
    ]
    parts = []

    for p in candidates:
        path = pathlib.Path(p)
        if path.exists():
            try:
                v = path.read_text(errors="ignore").strip()
                print(v)
                if v:
                    parts.append(v)
            except Exception:
                pass

    env_fp = os.getenv("LICENSE_FINGERPRINT")
    if env_fp:
        parts.append(env_fp.strip())

    if not parts:
        print("[LICENSE] 无法获取宿主机指纹", file=sys.stderr)
        return None

    raw = "||".join(parts)
    print('容器指纹')
    print(raw)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _verify_signature(pub_key, payload: dict, signature_b64: str) -> bool:
    try:
        sig = base64.b64decode(signature_b64)
    except Exception:
        print("[LICENSE] 签名不是合法 base64", file=sys.stderr)
        return False

    payload_bytes = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":")
    ).encode("utf-8")

    try:
        pub_key.verify(
            sig,
            payload_bytes,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except Exception as e:
        print(f"[LICENSE] 签名校验失败: {e}", file=sys.stderr)
        return False

def check_license() -> bool:
    if not LICENSE_PATH.exists():
        print("[LICENSE] 未找到 license.dat，拒绝启动", file=sys.stderr)
        return False

    try:
        lic = json.loads(LICENSE_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[LICENSE] 读取 license.dat 失败: {e}", file=sys.stderr)
        return False

    payload = lic.get("payload")
    signature = lic.get("signature")

    if not isinstance(payload, dict) or not isinstance(signature, str):
        print("[LICENSE] license 格式错误", file=sys.stderr)
        return False

    pub_key = _load_pub_key()
    if not pub_key:
        return False

    # 1. 签名校验
    if not _verify_signature(pub_key, payload, signature):
        return False

    # 2. 指纹校验
    real_fp = _get_fingerprint()
    if not real_fp:
        return False

    if payload.get("fingerprint") != real_fp:
        print(payload.get("fingerprint"))
        print(real_fp)
        print("[LICENSE] 当前机器未授权（指纹不匹配）", file=sys.stderr)
        return False

    # 3. 过期时间校验（有则校）
    exp = payload.get("expire_at")
    if exp:
        try:
            exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > exp_dt:
                print("[LICENSE] License 已过期", file=sys.stderr)
                return False
        except Exception:
            print("[LICENSE] 过期时间格式非法", file=sys.stderr)
            return False

    print("[LICENSE] License 校验通过", file=sys.stderr)
    return True

if __name__ == "__main__":
    ok = check_license()
    sys.exit(0 if ok else 1)
