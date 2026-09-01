"""
 @File: connect_info_encryptor.py
 @Description: 数据源连接信息加密模块
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-08-26

 使用 AES-256-GCM 对称加密算法加密数据源连接信息
 密钥由用户自行配置在环境变量中
 支持兼容模式：未加密的旧数据可以直接使用，加密后自动添加前缀标识
"""

import base64
import os
import secrets
import hashlib
import binascii
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class ConnectInfoEncryptor:
    """
    数据源连接信息加密器

    使用 AES-256-GCM 加密算法，这是一种带认证的加密模式：
    - 256位密钥提供高安全性
    - GCM 模式提供认证标签，防止篡改
    - 每次加密使用随机 nonce（12字节），确保相同明文产生不同密文

    加密后的数据格式: base64(nonce + ciphertext + auth_tag)
    """

    # 加密数据的前缀标识（用于区分加密和非加密数据）
    ENCRYPTED_PREFIX = "ENC$"

    # AES-256-GCM 要求的 nonce 长度（字节）
    NONCE_LENGTH = 12

    # 密钥长度（字节）
    KEY_LENGTH = 32

    _instance: Optional['ConnectInfoEncryptor'] = None

    def __new__(cls):
        """单例模式，确保整个应用使用同一个加密器实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._key: Optional[bytes] = None
        self._aesgcm: Optional[AESGCM] = None

        # 从环境变量获取密钥
        key_from_env = os.environ.get('CONNECT_INFO_MASTER_KEY')

        if not key_from_env:
            # 首次部署时自动生成密钥（仅提示，不自动保存）
            self._generate_and_warn()
        else:
            self._key = self._normalize_key(key_from_env)
            self._aesgcm = AESGCM(self._key)

    def _normalize_key(self, key: str) -> bytes:
        """
        将用户提供的密钥转换为32字节的密钥

        处理逻辑：
        - 如果密钥是 base64 编码的32字节随机数（推荐方式），直接解码
        - 如果密钥是普通字符串，使用 SHA-256 哈希来生成固定长度的密钥
        """
        try:
            # 尝试作为 base64 编码的密钥解码
            decoded = base64.b64decode(key)
            if len(decoded) == self.KEY_LENGTH:
                return decoded
            # 如果解码后长度不对，使用前32字节
            return decoded[:self.KEY_LENGTH]
        except Exception:
            # 不是有效的 base64 字符串，使用 SHA-256 哈希生成固定长度密钥
            return hashlib.sha256(key.encode()).digest()

    def _generate_and_warn(self):
        """生成新密钥并打印警告信息"""
        # 生成32字节随机密钥
        raw_key = secrets.token_bytes(self.KEY_LENGTH)
        self._key = raw_key
        self._aesgcm = AESGCM(self._key)

        # 将密钥转为 base64 便于复制
        key_b64 = base64.b64encode(raw_key).decode()

        warning_msg = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                         ⚠️  安全配置警告  ⚠️                                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  检测到 CONNECT_INFO_MASTER_KEY 未配置，系统已自动生成了一个临时密钥！           ║
║                                                                              ║
║  ⚠️  重要提醒：                                                              ║
║  1. 这个密钥仅保存在内存中，重启后会丢失！                                       ║
║  2. 重启后所有加密数据将无法解密！                                             ║
║  3. 请立即将以下密钥添加到你的 .env 文件中：                                    ║
║                                                                              ║
║  ══════════════════════════════════════════════════════════════════════════ ║
║  CONNECT_INFO_MASTER_KEY={key}
║  ══════════════════════════════════════════════════════════════════════════ ║
║                                                                              ║
║  📝 生成新密钥的方法：                                                         ║
║     python -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""".format(key=key_b64)

        print(warning_msg)

    def encrypt(self, plaintext: str) -> str:
        """
        加密明文数据

        Args:
            plaintext: 需要加密的原始字符串

        Returns:
            加密后的字符串，格式为 "ENC$" + base64(nonce + ciphertext)
        """
        if not plaintext:
            return plaintext

        if not self._key:
            raise ValueError("加密密钥未初始化")

        # 生成随机 nonce（12字节）
        nonce = secrets.token_bytes(self.NONCE_LENGTH)

        # 使用 AES-256-GCM 加密
        # 注意：GCM 模式会自动附加 16 字节的认证标签
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)

        # 组合 nonce + ciphertext（包含 auth_tag）
        combined = nonce + ciphertext

        # 返回 base64 编码并添加前缀
        return self.ENCRYPTED_PREFIX + base64.b64encode(combined).decode('ascii')

    def decrypt(self, encrypted: str) -> str:
        """
        解密数据

        Args:
            encrypted: 加密后的字符串

        Returns:
            解密后的原始字符串
        """
        if not encrypted:
            return encrypted

        # 检查是否加密数据
        if not encrypted.startswith(self.ENCRYPTED_PREFIX):
            # 兼容模式：未加密的数据直接返回
            return encrypted

        if not self._key:
            raise ValueError("加密密钥未初始化，请检查 CONNECT_INFO_MASTER_KEY 环境变量")

        # 移除前缀并解码
        encrypted_data = encrypted[len(self.ENCRYPTED_PREFIX):]
        combined = base64.b64decode(encrypted_data)

        # 分离 nonce 和 ciphertext
        nonce = combined[:self.NONCE_LENGTH]
        ciphertext = combined[self.NONCE_LENGTH:]

        # 解密
        plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)

        return plaintext.decode('utf-8')

    @property
    def has_key(self) -> bool:
        """检查是否已配置密钥"""
        return self._key is not None


# 全局实例获取函数
def get_encryptor() -> ConnectInfoEncryptor:
    """获取加密器单例实例"""
    return ConnectInfoEncryptor()


def encrypt_connect_info(plaintext: str) -> str:
    """
    加密连接信息的便捷函数

    Example:
        encrypted = encrypt_connect_info("postgresql://user:password@host:5432/db")
        # 返回: ENC$xxxxx...xxxxx
    """
    return get_encryptor().encrypt(plaintext)


def decrypt_connect_info(encrypted: str) -> str:
    """
    解密连接信息的便捷函数（兼容模式）

    Example:
        decrypted = decrypt_connect_info("ENC$xxxxx...xxxxx")
        # 返回: postgresql://user:password@host:5432/db

        # 旧数据（未加密）也直接返回原值
        decrypted = decrypt_connect_info("postgresql://user:password@host:5432/db")
        # 返回: postgresql://user:password@host:5432/db
    """
    return get_encryptor().decrypt(encrypted)


def is_encrypted(value: str) -> bool:
    """检查值是否已加密"""
    return bool(value and value.startswith(ConnectInfoEncryptor.ENCRYPTED_PREFIX))


def get_connect_info_hash(plaintext: str) -> str:
    """
    获取连接信息的稳定哈希值，用于快速匹配和去重

    注意：AES-GCM 加密每次使用随机 nonce，相同明文会产生不同的密文，
    因此无法直接用加密后的值进行匹配。这个哈希值提供了一个稳定的标识符。

    Args:
        plaintext: 原始连接信息字符串

    Returns:
        十六进制格式的 SHA256 哈希值（前32字符作为短标识）
    """
    if not plaintext:
        return ""
    return hashlib.sha256(plaintext.encode('utf-8')).hexdigest()


def generate_new_key() -> str:
    """
    生成新的加密密钥

    用于用户首次配置时生成密钥

    Example:
        key = generate_new_key()
        # 返回: k3H7xL9...（base64编码的32字节随机数）

        print(f"请将此密钥添加到 .env 文件：")
        print(f"CONNECT_INFO_MASTER_KEY={key}")
    """
    raw_key = secrets.token_bytes(ConnectInfoEncryptor.KEY_LENGTH)
    return base64.b64encode(raw_key).decode()
