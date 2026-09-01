import flask_login
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import UUID

from extensions.ext_database import db


class User(db.Model, flask_login.UserMixin):
    """
    用户模型

    注意：由于SQLAlchemy使用元类自动生成__init__方法，
    IDE类型检查器可能无法完全识别所有参数。
    以下字段均可作为构造参数使用。
    """

    __tablename__ = 'users'
    __table_args__ = (
        db.PrimaryKeyConstraint('id', name='user_pkeys'),
    )

    def __init__(
        self,
        username: str | None = None,
        nickname: str | None = None,
        email: str | None = None,
        password: str | None = None,
        password_salt: str | None = None,
        avatar: str | None = None,
        status: str | None = None,
        role: str | None = None,
        idp_user_id: str | None = None,
        idp_source: str | None = None,
        **kwargs,
    ):
        """显式签名，让 IDE 识别列名参数；运行时等价于 kwargs 形式。"""
        self.username = username
        self.nickname = nickname
        self.email = email
        self.password = password
        self.password_salt = password_salt
        self.avatar = avatar
        self.status = status
        self.role = role
        self.idp_user_id = idp_user_id
        self.idp_source = idp_source
        for k, v in kwargs.items():
            setattr(self, k, v)

    # 静态全局方法：创建用户的独立向量检索空间
    @staticmethod
    def build_weaviate_class_name(user_id) -> str:
        return f"datacard_datasource__{str(user_id).replace('-', '_')}"

    id = db.Column(UUID, server_default=db.text('uuid_generate_v4()'), comment='ID')
    user_group_id = db.Column(UUID, nullable=True, comment='用户组id')
    username = db.Column(db.String(32), comment='用户名（邮箱、账号等唯一标识）')
    nickname = db.Column(db.String(32), comment='昵称')
    email = db.Column(db.String(128), nullable=True, comment='邮箱')
    password = db.Column(db.String(128), comment='密码')
    password_salt = db.Column(db.String(32), comment='密码盐')
    weaviate_class_name = db.Column(db.String(128),nullable=True,comment='该用户绑定的 Weaviate 向量空间 class 名')
    avatar = db.Column(db.String(255), comment='头像')
    status = db.Column(db.String(32), comment='状态：normal、disabled')
    role = db.Column(db.String(32), comment='角色：normal、admin')
    last_login = db.Column(db.TIMESTAMP(timezone=True), comment='登录时间 utc')
    password_reset_at = db.Column(db.TIMESTAMP(timezone=True), comment='密码重置时间')
    created_at = db.Column(db.TIMESTAMP(timezone=True), server_default=func.current_timestamp(), comment='創建時間')
    updated_at = db.Column(db.TIMESTAMP(timezone=True), server_default=func.current_timestamp(),
                           onupdate=func.current_timestamp(), comment='更新時間')

    # SSO第三方登录字段
    idp_user_id = db.Column(db.String(128), nullable=True, index=True, comment='第三方用户ID（SSO来源）')
    idp_source = db.Column(db.String(64), nullable=True, index=True, comment='第三方来源标识（如企业A）')

    def is_authenticated(self):
        return True

    def is_active(self):
        return self.status == 'normal'

    def is_anonymous(self):
        return False

    def get_id(self):
        # 返回用户ID的unicode字符串。这里使用str确保兼容性
        return str(self.id)


class UserGroup(db.Model):
    __tablename__ = 'user_groups'
    __table_args__ = (
        db.PrimaryKeyConstraint('group_id', name='user_group_pkey'),
    )

    group_id = db.Column(UUID, server_default=db.text('uuid_generate_v4()'), comment='ID')
    # 创建者用户ID
    creator_user_id = db.Column(UUID, nullable=True, comment='用户id')
    group_name = db.Column(db.String(32), comment='名称')
    description = db.Column(db.Text, comment='用户组描述')
    created_at = db.Column(db.TIMESTAMP(timezone=True), server_default=func.current_timestamp(), comment='創建時間')
    updated_at = db.Column(db.TIMESTAMP(timezone=True), server_default=func.current_timestamp(),
                           onupdate=func.current_timestamp(), comment='更新時間')

