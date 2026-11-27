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
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from connect_info_key import connect_info_key


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

        self._key = connect_info_key(os.environ.get("CONNECT_INFO_MASTER_KEY"))
        self._aesgcm = AESGCM(self._key)
        self._initialized = True

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

        # 将 key 写入受控的持久配置，不在终端输出。
    """
    raw_key = secrets.token_bytes(ConnectInfoEncryptor.KEY_LENGTH)
    return base64.b64encode(raw_key).decode()
