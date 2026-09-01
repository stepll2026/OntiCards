import base64
import io
import secrets
from datetime import datetime

import flask_login
import pandas as pd
from flask import Blueprint
from flask import send_file, request
from flask_login import login_required, current_user
from flask_restful import Api, Resource, marshal_with, fields, reqparse

from core.password import hash_password
from extensions.ext_database import db
from models.users import UserGroup, User

user_group_bp = Blueprint('user_group_bp', __name__)
api = Api(user_group_bp)
class UserGroupAPI(Resource):

    @login_required
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('name', type=str, required=True, location='json')
        parser.add_argument('description', type=str, required=True, location='json')
        args = parser.parse_args()
        print(flask_login.current_user)
        # 校验当前用户是否是管理员
        if flask_login.current_user.role != 'admin':
            return {'message': '无权限创建用户组', 'code': 403}

        # 判断用户组是否存在
        if UserGroup.query.filter_by(group_name=args['name']).first():
            return {'message': '用户组已存在', 'code': 400}

        user_group = UserGroup(group_name=args['name'], creator_user_id=flask_login.current_user.id,description=args['description'])
        db.session.add(user_group)
        db.session.commit()

        return {'message': '用户组创建成功', 'code': 200, 'data': {'id': str(user_group.group_id)}}

    @login_required
    def put(self):
        parser = reqparse.RequestParser()
        parser.add_argument('id', type=str, required=True, location='json')
        parser.add_argument('name', type=str, required=True, location='json')
        parser.add_argument('description', type=str, required=True, location='json')
        args = parser.parse_args()

        # 校验当前用户是否是管理员
        if flask_login.current_user.role != 'admin':
            return {'message': '无权限', 'code': 403}

        user_group = UserGroup.query.filter_by(group_id=args['id']).first()
        if not user_group:
            return {'message': '用户组不存在', 'code': 400}

        if user_group.group_name == args['name']:
            return {'message': '用户组名称未变更', 'code': 400}

        user_group.group_name = args['name']
        user_group.description = args['description']
        db.session.commit()

        return {'message': '用户组更新成功', 'code': 200}

    @login_required
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('name', type=str, required=False, location='args')
        args = parser.parse_args()

        # 校验当前用户是否是管理员
        if flask_login.current_user.role != 'admin':
            return {'message': '无权限', 'code': 403}

        query = UserGroup.query
        if args['name']:
            query = query.filter(UserGroup.group_name.like(f"%{args['name']}%"))


        user_groups = query.order_by(UserGroup.created_at.asc()).all()
        result = []
        for group in user_groups:
            user_count = User.query.filter_by(user_group_id=group.group_id).count()
            result.append({
                'id': str(group.group_id),
                'name': group.group_name,
                'create_at': group.created_at.strftime('%Y-%m-%d %H:%M'),
                'user_count': user_count
            })

        return {'code': 200, 'data': result}

    def delete(self):
        parser = reqparse.RequestParser()
        parser.add_argument('id', type=str, required=True, location='json')
        args = parser.parse_args()

        # 校验当前用户是否是管理员
        if flask_login.current_user.role != 'admin':
            return {'message': '无权限', 'code': 403}

        user_group = UserGroup.query.filter_by(group_id=args['id']).first()
        if not user_group:
            return {'message': '用户组不存在', 'code': 404}

        User.query.filter_by(user_group_id=user_group.group_id).delete()
        db.session.delete(user_group)
        db.session.commit()

        return {'message': '用户组及其用户已删除', 'code': 200}

class PasswordResetAPI(Resource):

    @login_required
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('user_id', type=str, required=True, location='json')
        # parser.add_argument('old_password', type=str, required=True, location='json')
        parser.add_argument('new_password', type=str, required=True, location='json')
        args = parser.parse_args()

        # 校验当前用户是否是管理员
        if flask_login.current_user.role != 'admin':
            return {'message': '无权限', 'code': 403}

        # 查找用户
        user = User.query.filter_by(id=args['user_id']).first()
        if not user:
            return {'message': '用户不存在', 'code': 404}

        # 校验旧密码
        # old_password_hashed = hash_password(args['old_password'], base64.b64decode(user.password_salt))
        # if base64.b64encode(old_password_hashed).decode() != user.password:
        #     return {'message': '旧密码错误', 'code': 400}

        # 校验新密码格式
        # if not (3 <= len(args['new_password']) <= 20 and
        #         any(c.isalpha() for c in args['new_password']) and
        #         any(c.isdigit() for c in args['new_password']) and
        #         all(c.isalnum() or c in '_-' for c in args['new_password'])):

        if not (3 <= len(args['new_password']) <= 20):
            return {'message': '新密码格式不正确', 'code': 400}

        # 生成新密码盐并加密新密码
        salt = secrets.token_bytes(16)
        base64_salt = base64.b64encode(salt).decode()
        new_password_hashed = hash_password(args['new_password'], salt)
        base64_new_password_hashed = base64.b64encode(new_password_hashed).decode()

        # 更新用户密码
        user.password = base64_new_password_hashed
        user.password_salt = base64_salt
        user.reset_at = datetime.utcnow()
        db.session.commit()

        return {'message': '密码重置成功', 'code': 200}

class UserStatusAPI(Resource):

    @login_required
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('user_ids', type=list, required=True, location='json')
        parser.add_argument('status', type=str, required=True, location='json')
        args = parser.parse_args()

        # 校验当前用户是否是管理员
        if flask_login.current_user.role != 'admin':
            return {'message': '无权限', 'code': 403}

        # 校验状态值
        if args['status'] not in ['normal', 'disabled']:
            return {'message': '无效的状态值', 'code': 400}

        # 更新用户状态
        User.query.filter(User.id.in_(args['user_ids'])).update({'status': args['status']}, synchronize_session=False)
        db.session.commit()

        return {'message': 'The user status has been updated successfully', 'code': 200}

class UserGroupTransferAPI(Resource):
    @login_required
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('user_ids', type=list, required=True, location='json')
        parser.add_argument('user_group_id', type=str, required=True, location='json')
        args = parser.parse_args()

        # 校验当前用户是否是管理员
        if flask_login.current_user.role != 'admin':
            return {'message': '无权限', 'code': 403}

        # 校验用户组id是否存在
        user_group = UserGroup.query.filter_by(group_id=args['user_group_id']).first()
        if not user_group:
            return {'message': '用户组不存在', 'code': 404}

        # 更新用户的用户组id字段
        User.query.filter(User.id.in_(args['user_ids'])).update({'user_group_id': args['user_group_id']},
                                                                synchronize_session=False)
        db.session.commit()

        return {'message': '用户组转移成功', 'code': 200}

class UserImportAPI(Resource):

    # @login_required
    def get(self):
        # 校验当前用户是否是管理员
        # if flask_login.current_user.role != 'admin':
        #     return {'message': '无权限', 'code': 403}

        # 创建导入模板
        output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        df = pd.DataFrame(columns=['用户名', '全名', '邮箱', '密码', '用户组名称', '角色(normal/admin)'])
        df.to_excel(writer, index=False, sheet_name='模板')
        writer.close()
        output.seek(0)

        return send_file(output, download_name='导入用户模板.xlsx', as_attachment=True)

    @login_required
    def post(self):
        # 校验当前用户是否是管理员
        if flask_login.current_user.role != 'admin':
            return {'message': '无权限', 'code': 403}

        file = request.files['file']
        if not file or not file.filename.endswith(('.xls', '.xlsx')):
            return {'message': '文件格式不支持', 'code': 400}

        df = pd.read_excel(file)
        required_columns = ['用户名', '全名', '邮箱', '密码', '用户组名称', '角色(normal/admin)']
        if not all(column in df.columns for column in required_columns):
            return {'message': '文件表头不正确', 'code': 400}

        if len(df) > 2000:
            return {'message': '用户数不能超过2000', 'code': 400}

        users = []
        for _, row in df.iterrows():
            if row['角色(normal/admin)'] not in ['normal', 'admin']:
                return {'message': f"无效的角色: {row['角色(normal/admin)']}", 'code': 400}

            user_group = UserGroup.query.filter_by(group_name=row['用户组名称']).first()
            if not user_group:
                return {'message': f"用户组不存在: {row['用户组名称']}", 'code': 400}

            # 默认语言检测，允许为空
            # default_lang = row['默认语言(zh-CN/zh-HK/en,默认zh-HK)']
            # if pd.notna(default_lang):  # 检查是否为NaN
            #     if default_lang not in ['zh-CN', 'zh-HK', 'en']:
            #         return {'message': f"无效的默认语言: {default_lang}", 'code': 400}
            # else:
            #     default_lang = 'zh-HK'

            # if not (3 <= len(row['密码']) <= 20 and
            #         any(c.isalpha() for c in row['密码']) and
            #         any(c.isdigit() for c in row['密码']) and
            #         all(c.isalnum() or c in '_-' for c in row['密码'])):
            row_pwd = str(row['密码'])
            if not (3 <= len(row_pwd) <= 20):
                return {'message': f"密码格式不正确: {row_pwd}", 'code': 400}

            # if not all(c.isalnum() or c in '-_@' for c in row['用户名']):
            #     return {'message': f"用户名格式不正确: {row['用户名']}", 'code': 400}

            # 用户名是否存在
            if User.query.filter(db.func.lower(User.username) == row['用户名'].lower()).first():
                return {'message': f"用户名已存在: {row['用户名']}", 'code': 400}

            salt = secrets.token_bytes(16)
            base64_salt = base64.b64encode(salt).decode()
            password_hashed = hash_password(row_pwd, salt)
            base64_password_hashed = base64.b64encode(password_hashed).decode()

            user = User()
            user.username = row['用户名'].lower()
            user.nickname = row['全名']
            user.email = row['邮箱']
            user.password = base64_password_hashed
            user.password_salt = base64_salt
            user.user_group_id = user_group.group_id
            user.role = row['角色(normal/admin)']
            user.status = 'normal'
            users.append(user)

        db.session.bulk_save_objects(users)
        db.session.commit()

        return {'message': '用户导入成功', 'code': 200}

api.add_resource(UserImportAPI, '/user_import')
api.add_resource(UserGroupTransferAPI, '/user_group_transfer')
api.add_resource(UserStatusAPI, '/user_status')
api.add_resource(PasswordResetAPI, '/password_reset')
api.add_resource(UserGroupAPI, '/user_group')
