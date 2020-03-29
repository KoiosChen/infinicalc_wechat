from flask import current_app
from . import db, redis_db
import datetime
import os
import bleach
import uuid
import re
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from .common import session_commit
import sqlalchemy
import uuid
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import SQLAlchemyError

user_role = db.Table('user_role',
                     db.Column('user_id', db.String(64), db.ForeignKey('users.id'), primary_key=True),
                     db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
                     db.Column('create_at', db.DateTime, default=datetime.datetime.now))

role_menu = db.Table('role_menu',
                     db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
                     db.Column('menu_id', db.Integer, db.ForeignKey('menu.id'), primary_key=True),
                     db.Column('create_at', db.DateTime, default=datetime.datetime.now))


class OptionsDict(db.Model):
    __tablename__ = 'options_dic'
    id = db.Column(db.Integer, primary_key=True)
    # 字典名称
    name = db.Column(db.String(30), nullable=False, index=True)
    # 字典查询主键
    key = db.Column(db.String(80), nullable=False, index=True)
    label = db.Column(db.String(20), nullable=False, index=True)
    value = db.Column(db.String(5), nullable=False, index=True)
    order = db.Column(db.SmallInteger)
    status = db.Column(db.Boolean, default=True)
    selected = db.Column(db.Boolean, default=False)
    type = db.Column(db.String(20))
    memo = db.Column(db.String(100))
    __table_args__ = (UniqueConstraint('key', 'label', name='_key_label_combine'),)
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)


class Roles(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    default = db.Column(db.Boolean, default=False, index=True)
    menus = db.relationship(
        'Menu',
        secondary=role_menu,
        backref=db.backref(
            'role_menus',
            lazy='dynamic'
        )
    )

    def __repr__(self):
        return '<Role %r>' % self.name


class Menu(db.Model):
    __tablename__ = 'menu'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    icon = db.Column(db.String(50))
    url = db.Column(db.String(250))
    order = db.Column(db.SmallInteger, default=0)
    bg_color = db.Column(db.String(50))
    type = db.Column(db.String(20))
    permission = db.Column(db.Integer, db.ForeignKey('permissions.id'))
    parent_id = db.Column(db.Integer, db.ForeignKey('menu.id'))
    parent = db.relationship('Menu', backref="children", remote_side=[id])

    def __repr__(self):
        return '<Menu\'s name: %r>' % self.name


class Permissions(db.Model):
    __tablename__ = 'permissions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), index=True)
    action = db.Column(db.String(250), unique=True, index=True)
    menu = db.relationship('Menu', backref='permissions', lazy='dynamic')


class LoginInfo(db.Model):
    __tablename__ = 'login_info'
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(300), nullable=False)
    login_time = db.Column(db.Integer, nullable=False)
    platform = db.Column(db.String(20), nullable=False)
    login_ip = db.Column(db.String(64))
    user = db.Column(db.String(64), db.ForeignKey('users.id'))
    status = db.Column(db.Boolean, default=True)
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)


class Users(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
    email = db.Column(db.String(64), unique=True, index=True)
    phone = db.Column(db.String(15), unique=True, index=True)
    wechat_id = db.Column(db.String(50), unique=True, index=True)
    username = db.Column(db.String(64), index=True, unique=True)
    true_name = db.Column(db.String(30))
    # 0 unknown, 1 male, 2 female
    gender = db.Column(db.SmallInteger)
    roles = db.relationship(
        'Roles',
        secondary=user_role,
        backref=db.backref(
            'users'
        )
    )
    password_hash = db.Column(db.String(128))
    status = db.Column(db.SmallInteger)
    post = db.relationship('Post', backref='author', lazy='dynamic')
    address = db.Column(db.String(200))
    login_info = db.relationship('LoginInfo', backref='login_user', lazy='dynamic')

    @property
    def permissions(self):
        return Permissions.query.outerjoin(Menu).outerjoin(role_menu).outerjoin(Roles).outerjoin(user_role).outerjoin(
            Users).filter(Users.id.__eq__(self.id)).all()

    @property
    def menus(self):
        return Menu.query.outerjoin(role_menu).outerjoin(Roles).outerjoin(user_role).outerjoin(Users). \
            filter(
            Users.id == self.id
        ).order_by(Menu.order).all()

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)
        self.token = None

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def verify_code(self, message):
        """
        验证码
        :param message:
        :return:
        """
        login_key = f"{self.id}::{self.phone}::login_message"
        return True if redis_db.exists(login_key) and redis_db.get(login_key) == message else False

    def __repr__(self):
        return '<User %r>' % self.username


class City(db.Model):
    __tablename__ = 'city'
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(20), unique=True, index=True, nullable=False)
    province = db.Column(db.String(20), index=True)
    country = db.Column(db.String(20), default='中国')


class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    alarm_id = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.datetime.now)
    author_id = db.Column(db.String(64), db.ForeignKey('users.id'))
    body_html = db.Column(db.Text)

    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'blockquote', 'code',
                        'em', 'i', 'li', 'ol', 'pre', 'strong', 'ul',
                        'h1', 'h2', 'h3', 'p', 'img']
        attrs = {
            '*': ['class'],
            'a': ['href', 'rel'],
            'img': ['src', 'alt', 'width', 'height'],
        }
        target.body_html = bleach.clean(value, tags=allowed_tags, attributes=attrs, strip=True)


db.event.listen(Post.body, 'set', Post.on_changed_body)


class TokenRecord(db.Model):
    __tablename__ = 'token_record'
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(512), nullable=False)
    expire = db.Column(db.String(10))
    create_time = db.Column(db.DateTime)


aes_key = 'koiosr2d2c3p0000'

PermissionIP = redis_db.lrange('permission_ip', 0, -1)

PATH_PREFIX = os.path.abspath(os.path.dirname(__file__))

CONFIG_FILE_PATH = PATH_PREFIX + 'config_file/'

CACTI_PIC_FOLDER = PATH_PREFIX + '/static/cacti_pic/'

MailTemplate_Path_Tmp = os.path.join(PATH_PREFIX, 'mail_template/tmp')

MailTemplate_Path = os.path.join(PATH_PREFIX, 'mail_template')

UploadFile_Path_Tmp = os.path.join(PATH_PREFIX, 'upload_file/tmp')

UploadFile_Path = os.path.join(PATH_PREFIX, 'upload_file')

MailResult_Path = os.path.join(PATH_PREFIX, 'mail_result')

QRCode_PATH = os.path.join(PATH_PREFIX, 'qrcode_image')

Temp_File_Path = os.path.join(PATH_PREFIX, 'tmp')

REQUEST_RETRY_TIMES = 1
REQUEST_RETRY_TIMES_PER_TIME = 1
