import base64
import os
import secrets
import uuid
from datetime import datetime, timezone

import flask_login
from flask import Blueprint, request
from flask_login import login_required, current_user, logout_user, login_user
from flask_restful import Api, Resource, marshal_with, fields, reqparse
from sqlalchemy.exc import SQLAlchemyError

from controllers.weaviate_db_tool.weaviate_api import ensure_user_collection_exists, batch_delete_by_uuids, \
    drop_collection_by_class_name, weaviate_client
from core.passport import PassportService
from core.password import compare_password, hash_password
from extensions.ext_database import db
from models import users
from models.datacards_datasource import DataCardDataSource
from models.datasource_infos import DatasourceInfo
from models.user_datasource_schema import UserDatasourceSchema
from models.users import UserGroup, User
from models.global_inventory import (
    TargetInventoryJob,
    FieldMapping,
    TableRelationship,
    TableRelationshipCard
)

user_bp = Blueprint('users', __name__)
api = Api(user_bp)

user_info_fields = {
    'id': fields.String,
    'username': fields.String,
    'nickname': fields.String,
    'avatar': fields.String,
    'status': fields.String,
    'default_lang': fields.String,
    'user_group_name': fields.String,
    'email':fields.String,
    'role': fields.String,
    'login_at': fields.DateTime,
}

user_tetx = {
    'id':fields.String,
    'username':fields.Integer
}
user_info_response_fields = {
    'code': fields.Integer,
    'message': fields.String,
    'data': fields.Nested(user_info_fields),
}

# 定义所有用户列表返回字段
user_list_response_fields = {
    'code': fields.Integer,
    'message': fields.String,
    'data': fields.List(fields.Nested(user_info_fields)),
}

#用户信息修改以及获取
class UserAPI(Resource):

    @login_required
    def get(self):
        print('6265623623')
        user = current_user
        user_group_name = None
        if user.user_group_id:
            user_group = UserGroup.query.get(user.user_group_id)
            if user_group:
                user_group_name = user_group.group_name

        return {
            'code': 200,
            'message': '获取用户信息成功',
            'data': {
                'id': str(user.id),
                'username': user.username,
                'nickname': user.nickname,
                'avatar': user.avatar,
                'user_group_name': user_group_name,
                'role': user.role,
                'email':user.email,
                'login_at': str(user.last_login),
            }
        }

    # 更新当前登录用户信息
    @login_required
    def put(self):
        parser = reqparse.RequestParser()
        parser.add_argument('nickname', type=str, required=False, location='json')
        parser.add_argument('avatar', type=str, required=False, location='json')
        parser.add_argument('email', type=str, required=False, location='json')
        parser.add_argument('password', type=str, required=False, location='json')
        args = parser.parse_args()

        user = flask_login.current_user

        # 更新昵称
        if args.get('nickname'):
            user.nickname = args['nickname']

        # 更新头像
        if args.get('avatar'):
            user.avatar = args['avatar']

        # 更新邮箱
        if args.get('email'):
            # 检查邮箱是否已被其他用户使用
            existing_email = User.query.filter(
                User.email == args['email'],
                User.id != user.id
            ).first()
            if existing_email:
                return {'message': '邮箱已被其他用户使用', 'code': 400}
            user.email = args['email']

        # 更新密码
        if args.get('password'):
            # 生成新密码
            salt = secrets.token_bytes(16)
            base64_salt = base64.b64encode(salt).decode()
            password_hashed = hash_password(args['password'], salt)
            base64_password_hashed = base64.b64encode(password_hashed).decode()

            user.password = base64_password_hashed
            user.password_salt = base64_salt
            user.password_reset_at = datetime.now(timezone.utc)

        db.session.commit()

        return {'message': '用户信息更新成功', 'code': 200}

#用户退出
class LogoutAPI(Resource):

    @login_required
    def get(self):
        logout_user()
        return {'message': 'Logged out successfully', 'code': 200}

#登录注册
class LoginAPI(Resource):
    # 登录成功
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('username', type=str, required=True, location='json')
        parser.add_argument('password', type=str, required=True, location='json')
        args = parser.parse_args()

        password = args['password']

        # 用户名不分大小写
        user = User.query.filter(db.func.lower(User.username) == args['username'].lower()).first()
        if user:
            if user.password is None or not compare_password(password, user.password, user.password_salt):
                return {'message': 'Invalid username or password', 'code': 400}
        else:
            return {'message': 'Invalid username or password', 'code': 400}

        # 状态检查
        if user.status != 'normal':
            return {'message': 'Account has been disabled, please contact the administrator', 'code': 400}

        login_user(user)

        token = PassportService.get_account_jwt_token(user)

        user.last_login = db.func.current_timestamp()
        db.session.commit()

        return {'message': 'Login successful', 'code': 200, 'data': {'token': token}}

    # 注册
    def put(self):
        parser = reqparse.RequestParser()
        parser.add_argument('username', type=str, required=True, location='json')
        parser.add_argument('password', type=str, required=True, location='json')
        args = parser.parse_args()
        print(args)

        new_password = args['password']

        user = User.query.filter_by(username=args['username']).first()
        if user:
            return {'message': 'User already exists', 'code': 400}

        # generate password salt
        salt = secrets.token_bytes(16)
        base64_salt = base64.b64encode(salt).decode()

        # encrypt password with salt
        password_hashed = hash_password(new_password, salt)
        base64_password_hashed = base64.b64encode(password_hashed).decode()

        user = User()
        user.username = args['username']
        user.password = base64_password_hashed
        user.password_salt = base64_salt
        user.status = 'normal'
        user.nickname = args['username']
        db.session.add(user)

        db.session.flush()  # 让 user.id 立刻生成（不提交）
        user.weaviate_class_name = User.build_weaviate_class_name(user.id)

        # 创建用户的独立向量检索空间(Weaviate中生成对应Class的Collection)
        ensure_user_collection_exists(user.weaviate_class_name)

        db.session.commit()

        return {'message': 'Registration successful', 'code': 200}

#修改密码
class ChangePasswordAPI(Resource):

    @login_required
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('id', type=str, required=True, location='json')
        parser.add_argument('old_password', type=str, required=True, location='json')
        parser.add_argument('new_password', type=str, required=True, location='json')
        args = parser.parse_args()

        user = db.session.query(User).filter_by(id=args['id']).first()
        if not user or not compare_password(args['old_password'], user.password, user.password_salt):
            return {'message': 'Old password is incorrect or user does not exist', 'code': 400}

        # generate new password salt
        salt = secrets.token_bytes(16)
        base64_salt = base64.b64encode(salt).decode()

        # encrypt new password with new salt
        password_hashed = hash_password(args['new_password'], salt)
        base64_password_hashed = base64.b64encode(password_hashed).decode()

        user.password = base64_password_hashed
        user.password_salt = base64_salt
        user.password_reset_at = datetime.now(timezone.utc)
        db.session.commit()

        return {'message': 'Password changed successfully', 'code': 200}


# ==================== 用户头像上传配置 ====================
# 注意：头像上传功能为可选功能，不影响用户注册和基本功能
# 头像上传目录（使用项目根目录下的 storage/avatars）
try:
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'storage', 'avatars')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    # 确保上传目录存在（只在需要时创建）
    # 注意：目录创建延迟到实际上传时进行，不影响模块导入
except Exception as e:
    # 如果路径配置失败，设置为None，上传时会提示功能不可用
    UPLOAD_FOLDER = None
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    print(f"[警告] 头像上传路径配置失败: {e}，头像上传功能将不可用")


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_avatar_url(filename):
    """
    生成头像访问URL
    注意：需要在 Flask 路由中配置静态文件访问路径
    例如：@app.route('/console/api/imgs/<filename>')
    """
    # 使用相对路径，由前端或网关配置完整域名
    return f'/console/api/imgs/{filename}'


def ensure_upload_folder():
    """确保上传目录存在（延迟创建，只在实际上传时调用）"""
    if UPLOAD_FOLDER is None:
        raise ValueError("头像上传功能未配置")
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)


class UploadAvatarAPI(Resource):
    def post(self):
        try:
            # 确保上传目录存在
            ensure_upload_folder()
        except ValueError as e:
            return {'message': str(e), 'code': 400}

        file = request.files.get('file')
        user_id = request.form.get('user_id')
        if file.filename == '':
            return {'message': 'No file selected', 'code': 400}

        if file and allowed_file(file.filename):
            user = User.query.filter_by(id=user_id).first()
            if not user:
                return {'message': 'User does not exist', 'code': 404}

            filename = file.filename
            ext = filename.rsplit('.', 1)[1].lower()
            new_filename = f"{uuid.uuid4().hex}.{ext}"
            file_path = os.path.join(UPLOAD_FOLDER, new_filename)
            file.save(file_path)
            img_href = get_avatar_url(new_filename)
            user.avatar = img_href
            # 数据库保存相对路径或文件名
            # user.avatar = f"{UPLOAD_FOLDER}/{new_filename}"
            db.session.commit()

            return {
                'message': 'Avatar uploaded successfully',
                'code': 200,
                'data': {
                    'avatar_url': img_href
                }
            }
        else:
            return {'message': 'Unsupported file format', 'code': 400}

    def put(self):
        try:
            # 确保上传目录存在
            ensure_upload_folder()
        except ValueError as e:
            return {'message': str(e), 'code': 400}

        file = request.files.get('file')
        user_id = request.form.get('user_id')

        if not file or file.filename == '':
            return {'message': 'No file selected', 'code': 400}

        if not allowed_file(file.filename):
            return {'message': 'Unsupported file format', 'code': 400}

        user = User.query.filter_by(id=user_id).first()
        if not user:
            return {'message': 'User does not exist', 'code': 404}


        # 保存新头像
        filename = file.filename
        ext = filename.rsplit('.', 1)[1].lower()
        new_filename = f"{uuid.uuid4().hex}.{ext}"
        file_path = os.path.join(UPLOAD_FOLDER, new_filename)
        file.save(file_path)

        # 更新头像路径
        img_href = get_avatar_url(new_filename)
        user.avatar = img_href
        db.session.commit()

        return {
            'message': 'Avatar updated successfully',
            'code': 200,
            'data': {
                'avatar_url': img_href
            }
        }

# 获取所有用户信息接口
class AllUsersAPI(Resource):
    @login_required  # 如果不需要登录访问，可以删除这一行
    @marshal_with(user_list_response_fields)
    def get(self):
        users = User.query.all()
        result = []
        for user in users:
            user_group_name = None
            if user.user_group_id:
                user_group = db.session.get(UserGroup, user.user_group_id)
                if user_group:
                    user_group_name = user_group.group_name

            result.append({
                'id': str(user.id),
                'username': user.username,
                'nickname': user.nickname,
                'status':user.status,
                'avatar': user.avatar,
                'default_lang': getattr(user, 'default_lang', None),
                'user_group_name': user_group_name,
                'email': user.email,
                'role': user.role,
                'login_at': user.last_login,
            })

        return {'code': 200, 'message': '获取所有用户成功', 'data': result}


# 用户管理接口（增删改）
class UserManagementAPI(Resource):
    """
    用户管理资源类
    POST: 新增用户
    PUT: 修改用户信息
    DELETE: 删除用户
    """
    
    @login_required
    def post(self):
        """
        新增用户
        必填参数: username, password
        可选参数: nickname, email, role, status, user_group_id, avatar
        """
        parser = reqparse.RequestParser()
        parser.add_argument('username', type=str, required=True, location='json', help='用户名不能为空')
        parser.add_argument('password', type=str, required=True, location='json', help='密码不能为空')
        parser.add_argument('nickname', type=str, required=False, location='json')
        parser.add_argument('email', type=str, required=False, location='json')
        parser.add_argument('role', type=str, required=False, location='json', default='normal')
        parser.add_argument('status', type=str, required=False, location='json', default='normal')
        parser.add_argument('user_group_id', type=str, required=False, location='json')
        parser.add_argument('avatar', type=str, required=False, location='json')
        args = parser.parse_args()

        # 检查用户名是否已存在
        existing_user = User.query.filter(db.func.lower(User.username) == args['username'].lower()).first()
        if existing_user:
            return {'message': '用户名已存在', 'code': 400}

        # 检查邮箱是否已存在（如果提供了邮箱）
        if args.get('email'):
            existing_email = User.query.filter_by(email=args['email']).first()
            if existing_email:
                return {'message': '邮箱已被使用', 'code': 400}

        # 验证角色和状态值
        if args['role'] not in ['normal', 'admin']:
            return {'message': '角色值无效，仅支持 normal 或 admin', 'code': 400}
        
        if args['status'] not in ['normal', 'disabled']:
            return {'message': '状态值无效，仅支持 normal 或 disabled', 'code': 400}

        # 验证用户组ID是否存在（如果提供了）
        if args.get('user_group_id'):
            user_group = UserGroup.query.get(args['user_group_id'])
            if not user_group:
                return {'message': '用户组不存在', 'code': 400}

        # 生成密码盐和加密密码
        salt = secrets.token_bytes(16)
        base64_salt = base64.b64encode(salt).decode()
        password_hashed = hash_password(args['password'], salt)
        base64_password_hashed = base64.b64encode(password_hashed).decode()

        # 创建新用户
        new_user = User()
        new_user.username = args['username']
        new_user.password = base64_password_hashed
        new_user.password_salt = base64_salt
        new_user.nickname = args.get('nickname', args['username'])  # 默认使用用户名作为昵称
        new_user.email = args.get('email')
        new_user.role = args['role']
        new_user.status = args['status']
        new_user.user_group_id = args.get('user_group_id')
        new_user.avatar = args.get('avatar')

        try:
            db.session.add(new_user)

            db.session.flush()  # user_id生效
            new_user.weaviate_class_name = User.build_weaviate_class_name(new_user.id)

            # 创建用户的独立向量检索空间(Weaviate中生成对应Class的Collection)
            ensure_user_collection_exists(new_user.weaviate_class_name)

            db.session.commit()
            return {
                'message': '用户创建成功',
                'code': 200,
                'data': {
                    'id': str(new_user.id),
                    'username': new_user.username,
                    'nickname': new_user.nickname,
                    'email': new_user.email,
                    'role': new_user.role,
                    'status': new_user.status
                }
            }
        except Exception as e:
            db.session.rollback()
            return {'message': f'用户创建失败: {str(e)}', 'code': 500}

    @login_required
    def put(self):
        """
        修改用户信息
        必填参数: id
        可选参数: nickname, email, password, status, role
        """
        parser = reqparse.RequestParser()
        parser.add_argument('id', type=str, required=True, location='json', help='用户ID不能为空')
        parser.add_argument('nickname', type=str, required=False, location='json')
        parser.add_argument('email', type=str, required=False, location='json')
        parser.add_argument('password', type=str, required=False, location='json')
        parser.add_argument('status', type=str, required=False, location='json')
        parser.add_argument('role', type=str, required=False, location='json')
        args = parser.parse_args()

        # 查找用户
        user = User.query.filter_by(id=args['id']).first()
        if not user:
            return {'message': '用户不存在', 'code': 404}

        # 验证状态值（如果提供了）
        if args.get('status') and args['status'] not in ['normal', 'disabled']:
            return {'message': '状态值无效，仅支持 normal 或 disabled', 'code': 400}

        # 验证角色值（如果提供了）
        if args.get('role') and args['role'] not in ['normal', 'admin']:
            return {'message': '角色值无效，仅支持 normal 或 admin', 'code': 400}

        # 更新邮箱（如果提供了）
        if args.get('email'):
            # 检查邮箱是否已被其他用户使用
            existing_email = User.query.filter(
                User.email == args['email'],
                User.id != args['id']
            ).first()
            if existing_email:
                return {'message': '邮箱已被其他用户使用', 'code': 400}
            user.email = args['email']

        # 更新昵称
        if args.get('nickname'):
            user.nickname = args['nickname']

        # 更新密码
        if args.get('password'):
            # 生成新的密码盐和加密密码
            salt = secrets.token_bytes(16)
            base64_salt = base64.b64encode(salt).decode()
            password_hashed = hash_password(args['password'], salt)
            base64_password_hashed = base64.b64encode(password_hashed).decode()

            user.password = base64_password_hashed
            user.password_salt = base64_salt
            user.password_reset_at = datetime.now(timezone.utc)

        # 更新状态
        if args.get('status'):
            user.status = args['status']

        # 更新角色
        if args.get('role'):
            user.role = args['role']

        try:
            db.session.commit()
            return {
                'message': '用户信息更新成功',
                'code': 200,
                'data': {
                    'id': str(user.id),
                    'username': user.username,
                    'nickname': user.nickname,
                    'status': user.status,
                    'role': user.role,
                    'email': user.email
                }
            }
        except Exception as e:
            db.session.rollback()
            return {'message': f'用户信息更新失败: {str(e)}', 'code': 500}

    @login_required
    def delete(self):
        """
        删除用户
        必填参数: id
        """
        parser = reqparse.RequestParser()
        parser.add_argument('id', type=str, required=True, location='json', help='用户ID不能为空')
        args = parser.parse_args()

        # 查找用户
        user = User.query.filter_by(id=args['id']).first()
        if not user:
            return {'message': '用户不存在', 'code': 404}

        # 防止删除当前登录用户
        if str(current_user.id) == args['id']:
            return {'message': '不能删除当前登录的用户', 'code': 400}

        try:
            deleted_username = user.username
            target_user_id = str(user.id)
            target_class = getattr(user, "weaviate_class_name", None)

            # ===== 1) 预取：该用户所有数据源ID、schema_id（doc_id）与 w_uuid =====
            # 1.1 获取该用户的所有数据源ID
            datasource_rows = (
                db.session.query(DatasourceInfo.id)
                .filter(DatasourceInfo.user_id == target_user_id)
                .all()
            )
            user_datasource_ids = [str(r[0]) for r in datasource_rows]

            # 1.2 获取所有 schema_id（doc_id）
            schema_rows = (
                db.session.query(UserDatasourceSchema.id)
                .filter(UserDatasourceSchema.user_id == target_user_id)
                .all()
            )
            schema_doc_ids = [str(r[0]) for r in schema_rows]

            # 1.3 获取所有 w_uuid（用于删除向量）
            w_uuids = []
            if schema_doc_ids:
                w_uuids = [
                    r[0] for r in db.session.query(DataCardDataSource.w_uuid)
                    .filter(DataCardDataSource.doc_id.in_(schema_doc_ids))
                    .all()
                    if r and r[0]
                ]

            # ===== 2) 数据库内事务：删除所有相关数据 =====
            # 2.0 治理报告相关数据清理（先清理文件记录和物理文件）
            governance_deleted = {
                'reports': 0,
                'report_files': 0,
                'rule_libraries': 0,
                'rules': 0,
                'rule_execution_results': 0,
                'physical_files_deleted': 0,
                'physical_files_not_found': [],
            }

            # 2.0.0 查询并统计规则库和规则数量（删除 datasource_infos 时会通过 CASCADE 自动删除）
            if user_datasource_ids:
                from models.governance_report import GovernanceReport
                from models.governance_rule import GovernanceRule
                from models.governance_rule_library import GovernanceRuleLibrary

                # 统计规则库数量（通过 datasource_id）
                governance_deleted['rule_libraries'] = db.session.query(GovernanceRuleLibrary).filter(
                    GovernanceRuleLibrary.datasource_id.in_(user_datasource_ids)
                ).delete(synchronize_session=False)

                # 统计规则数量（通过 library_id）
                governance_deleted['rules'] = db.session.query(GovernanceRule).filter(
                    GovernanceRule.library_id.in_(
                        db.session.query(GovernanceRuleLibrary.id).filter(
                            GovernanceRuleLibrary.datasource_id.in_(user_datasource_ids)
                        )
                    )
                ).delete(synchronize_session=False)

            # 2.0.1 查询该用户的所有报告ID
            from models.governance_report_file import GovernanceReportFile
            user_report_ids = [
                str(r[0]) for r in db.session.query(GovernanceReport.id)
                .filter(GovernanceReport.user_id == target_user_id)
                .all()
            ]

            if user_report_ids:
                # 2.0.2 查询并删除该用户所有报告产生的物理文件
                user_report_files = GovernanceReportFile.query.filter(
                    GovernanceReportFile.user_id == target_user_id
                ).all()
                governance_deleted['report_files'] = len(user_report_files)

                for rf in user_report_files:
                    try:
                        import os as os_module
                        file_path = rf.file_path.replace('/', os_module.sep)
                        if os_module.path.exists(file_path):
                            os_module.remove(file_path)
                            governance_deleted['physical_files_deleted'] += 1
                        else:
                            governance_deleted['physical_files_not_found'].append(rf.file_path)
                    except Exception as e:
                        print(f"[UserDelete] 删除治理文件失败: {rf.file_path}, error={e}")

                # 2.0.3 删除治理报告文件记录（会通过 CASCADE 自动清理）
                db.session.query(GovernanceReportFile).filter(
                    GovernanceReportFile.user_id == target_user_id
                ).delete(synchronize_session=False)

                # 2.0.4 删除治理报告（会通过 CASCADE 自动删除 rule_execution_results）
                deleted_reports = db.session.query(GovernanceReport).filter(
                    GovernanceReport.user_id == target_user_id
                ).delete(synchronize_session=False)
                governance_deleted['reports'] = deleted_reports

            # 2.0.5 清理用户的导出目录（如果存在）
            export_dir_deleted_ok = False
            try:
                from flask import current_app
                base_export_path = current_app.config.get(
                    'GOVERNANCE_EXPORT_PATH',
                    None
                )
                if base_export_path:
                    user_export_dir = os_module.path.join(base_export_path, target_user_id)
                    user_export_dir = user_export_dir.replace('\\', '/')
                    if os_module.path.exists(user_export_dir):
                        import shutil
                        shutil.rmtree(user_export_dir)
                        export_dir_deleted_ok = True
                        print(f"[UserDelete] 用户导出目录已删除: {user_export_dir}")
            except Exception as e:
                print(f"[UserDelete] 删除用户导出目录失败: error={e}")

            # 2.1 删除盘点相关数据（按用户数据源ID）
            inventory_deleted = {
                'target_inventory_jobs': 0,
                'field_mappings': 0,
                'table_relationships': 0,
                'table_relationship_cards': 0
            }

            if user_datasource_ids:
                # 2.1.1 删除定向盘点任务（会级联删除 TargetInventoryJobResult）
                deleted_jobs = db.session.query(TargetInventoryJob) \
                    .filter(TargetInventoryJob.user_id == target_user_id) \
                    .delete(synchronize_session=False)
                inventory_deleted['target_inventory_jobs'] = deleted_jobs

                # 2.1.2 删除字段映射
                deleted_mappings = db.session.query(FieldMapping) \
                    .filter(FieldMapping.datasource_id.in_(user_datasource_ids)) \
                    .delete(synchronize_session=False)
                inventory_deleted['field_mappings'] = deleted_mappings

                # 2.1.3 删除表关系（table_a 或 table_b 属于该用户的数据源）
                deleted_relationships = db.session.query(TableRelationship) \
                    .filter(
                        (TableRelationship.table_a_datasource_id.in_(user_datasource_ids)) |
                        (TableRelationship.table_b_datasource_id.in_(user_datasource_ids))
                    ) \
                    .delete(synchronize_session=False)
                inventory_deleted['table_relationships'] = deleted_relationships

                # 2.1.4 删除表关系卡片（不需要删除向量库，因为关系卡片不存向量库）
                deleted_cards = db.session.query(TableRelationshipCard) \
                    .filter(TableRelationshipCard.datasource_id.in_(user_datasource_ids)) \
                    .delete(synchronize_session=False)
                inventory_deleted['table_relationship_cards'] = deleted_cards

            # 2.2 删除数据卡片（按 doc_id）
            if schema_doc_ids:
                db.session.query(DataCardDataSource) \
                    .filter(DataCardDataSource.doc_id.in_(schema_doc_ids)) \
                    .delete(synchronize_session=False)

            # 2.3 删除 user_datasource_schemas（按 user_id）
            db.session.query(UserDatasourceSchema) \
                .filter(UserDatasourceSchema.user_id == target_user_id) \
                .delete(synchronize_session=False)

            # 2.4 删除 datasource_infos（按 user_id）
            db.session.query(DatasourceInfo) \
                .filter(DatasourceInfo.user_id == target_user_id) \
                .delete(synchronize_session=False)

            # 2.5 最后删除 user
            db.session.delete(user)

            db.session.commit()

        except SQLAlchemyError as e:
            db.session.rollback()
            return {'message': f'用户删除失败(数据库回滚): {str(e)}', 'code': 500}

            # ===== 3) 删除向量（提交后做，避免 DB 与 Weaviate 强耦合回滚）=====
        vectors_deleted_ok = True
        try:
            if w_uuids:
                batch_delete_by_uuids(w_uuids, class_name=target_class)
        except Exception as e:
            vectors_deleted_ok = False
            print(f"[UserDelete] delete vectors failed: user_id={target_user_id} class={target_class} err={e}")

        # ===== 4) 删除整个 class（提交后做）=====
        class_deleted_ok = True
        try:
            if target_class:
                drop_collection_by_class_name(target_class)
            else:
                class_deleted_ok = False
                print(f"[UserDelete] weaviate_class_name is empty: user_id={target_user_id}")
        except Exception as e:
            class_deleted_ok = False
            print(f"[UserDelete] drop class failed: user_id={target_user_id} class={target_class} err={e}")

        # ===== 5) 删除字段画像向量检索空间（如果存在）=====
        field_index_deleted_ok = False
        field_index_class = None
        if target_class:
            field_index_class = f"{target_class}__field_index"
            try:
                # 检查字段画像向量检索空间是否存在
                with weaviate_client() as client:
                    if client.collections.exists(field_index_class):
                        drop_collection_by_class_name(field_index_class)
                        field_index_deleted_ok = True
                        print(f"[UserDelete] field_index class deleted: {field_index_class}")
                    else:
                        print(f"[UserDelete] field_index class not exists, skip: {field_index_class}")
            except Exception as e:
                print(f"[UserDelete] drop field_index class failed: user_id={target_user_id} class={field_index_class} err={e}")

        return {
            'message': '用户删除成功',
            'code': 200,
            'data': {
                'deleted_username': deleted_username,
                'datasource_deleted': len(user_datasource_ids),
                'schemas_deleted': len(schema_doc_ids),
                'cards_vectors': len(w_uuids),
                'vectors_deleted': bool(vectors_deleted_ok),
                'class_deleted': bool(class_deleted_ok),
                'field_index_deleted': bool(field_index_deleted_ok),
                'weaviate_class_name': target_class,
                'field_index_class_name': field_index_class,
                # 治理报告相关数据删除统计
                'governance_deleted': {
                    **governance_deleted,
                    'export_dir_deleted': export_dir_deleted_ok,
                },
                # 盘点相关数据删除统计
                'inventory_deleted': inventory_deleted,
            }
        }

api.add_resource(UploadAvatarAPI, '/avatar')
#修改密码
api.add_resource(ChangePasswordAPI, '/change_password')
#登陆注册
api.add_resource(LoginAPI, '/login')
#退出登录
api.add_resource(LogoutAPI, '/logout')
#用户信息获取
api.add_resource(UserAPI, '/user')
# 获取所有用户信息
api.add_resource(AllUsersAPI, '/users/all')
# 用户管理接口（增删改）
api.add_resource(UserManagementAPI, '/users/manage')
