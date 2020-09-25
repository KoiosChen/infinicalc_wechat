from flask import current_app
from . import db, redis_db
import datetime
import os
import bleach
import re
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from .common import session_commit
import sqlalchemy
import uuid
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.mysql import LONGTEXT
import random


def make_uuid():
    return str(uuid.uuid4())


def make_order_id(prefix=None):
    """
    生成订单号
    :return:
    """
    date = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    # 生成4为随机数作为订单号的一部分
    random_str = str(random.randint(1, 9999))
    random_str = random_str.rjust(4, '0')
    rtn = '%s%s' % (date, random_str)
    return rtn if prefix is None else prefix + rtn


user_role = db.Table('user_role',
                     db.Column('user_id', db.String(64), db.ForeignKey('users.id'), primary_key=True),
                     db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
                     db.Column('create_at', db.DateTime, default=datetime.datetime.now))

customer_role = db.Table('customer_role',
                         db.Column('customer_id', db.String(64), db.ForeignKey('customers.id'), primary_key=True),
                         db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
                         db.Column('create_at', db.DateTime, default=datetime.datetime.now))

roles_elements = db.Table('roles_elements',
                          db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
                          db.Column('element_id', db.Integer, db.ForeignKey('elements.id'), primary_key=True),
                          db.Column('create_at', db.DateTime, default=datetime.datetime.now))

spu_standards = db.Table('spu_standards',
                         db.Column('spu_id', db.String(64), db.ForeignKey('spu.id'), primary_key=True),
                         db.Column('standards_id', db.String(64), db.ForeignKey('standards.id'),
                                   primary_key=True),
                         db.Column('create_at', db.DateTime, default=datetime.datetime.now))

sku_standardvalue = db.Table('sku_standardvalue',
                             db.Column('sku_id', db.String(64), db.ForeignKey('sku.id'), primary_key=True),
                             db.Column('standardvalue_id', db.String(64), db.ForeignKey('standard_value.id'),
                                       primary_key=True),
                             db.Column('create_at', db.DateTime, default=datetime.datetime.now))

sku_obj = db.Table('sku_obj',
                   db.Column('sku_id', db.String(64), db.ForeignKey('sku.id'), primary_key=True),
                   db.Column('obj_id', db.String(64), db.ForeignKey('obj_storage.id'), primary_key=True),
                   db.Column('create_at', db.DateTime, default=datetime.datetime.now))

spu_obj = db.Table('spu_obj',
                   db.Column('spu_id', db.String(64), db.ForeignKey('spu.id'), primary_key=True),
                   db.Column('obj_id', db.String(64), db.ForeignKey('obj_storage.id'), primary_key=True),
                   db.Column('create_at', db.DateTime, default=datetime.datetime.now))

cargo_obj = db.Table('cargo_obj',
                     db.Column('cargo_id', db.String(64), db.ForeignKey('total_cargoes.id'), primary_key=True),
                     db.Column('obj_id', db.String(64), db.ForeignKey('obj_storage.id'), primary_key=True),
                     db.Column('create_at', db.DateTime, default=datetime.datetime.now))

sku_shoporders = db.Table('sku_shoporders',
                          db.Column('sku_id', db.String(64), db.ForeignKey('sku.id'), primary_key=True),
                          db.Column('shoporders_id', db.String(64), db.ForeignKey('shop_orders.id'), primary_key=True),
                          db.Column('create_at', db.DateTime, default=datetime.datetime.now))

benefits_gifts = db.Table('benefits_gifts',
                          db.Column('benefits_id', db.String(64), db.ForeignKey('benefits.id'), primary_key=True),
                          db.Column('gifts_id', db.String(64), db.ForeignKey('gifts.id'), primary_key=True),
                          db.Column('create_at', db.DateTime, default=datetime.datetime.now))

promotions_benefits = db.Table('promotions_benefits',
                               db.Column('promotions_id', db.String(64), db.ForeignKey('promotions.id'),
                                         primary_key=True),
                               db.Column('benefits_id', db.String(64), db.ForeignKey('benefits.id'), primary_key=True),
                               db.Column('create_at', db.DateTime, default=datetime.datetime.now))

promotions_brands = db.Table('promotions_brands',
                             db.Column('promotions_id', db.String(64), db.ForeignKey('promotions.id'),
                                       primary_key=True),
                             db.Column('brands_id', db.String(64), db.ForeignKey('brands.id'), primary_key=True),
                             db.Column('create_at', db.DateTime, default=datetime.datetime.now))

promotions_spu = db.Table('promotions_spu',
                          db.Column('promotions_id', db.String(64), db.ForeignKey('promotions.id'), primary_key=True),
                          db.Column('spu_id', db.String(64), db.ForeignKey('spu.id'), primary_key=True),
                          db.Column('create_at', db.DateTime, default=datetime.datetime.now))

promotions_sku = db.Table('promotions_sku',
                          db.Column('promotions_id', db.String(64), db.ForeignKey('promotions.id'), primary_key=True),
                          db.Column('sku_id', db.String(64), db.ForeignKey('sku.id'), primary_key=True),
                          db.Column('create_at', db.DateTime, default=datetime.datetime.now))

promotions_classifies = db.Table('promotions_classifies',
                                 db.Column('promotions_id', db.String(64), db.ForeignKey('promotions.id'),
                                           primary_key=True),
                                 db.Column('classifies_id', db.String(64), db.ForeignKey('classifies.id'),
                                           primary_key=True),
                                 db.Column('create_at', db.DateTime, default=datetime.datetime.now))

itemsorders_benefits = db.Table('itemsorders_benefits',
                                db.Column('itemsorders_id', db.String(64), db.ForeignKey('items_orders.id'),
                                          primary_key=True),
                                db.Column('benefits_id', db.String(64), db.ForeignKey('benefits.id'),
                                          primary_key=True),
                                db.Column('create_at', db.DateTime, default=datetime.datetime.now))

scene_member_cards = db.Table('scene_member_cards',
                              db.Column('scene_invitation_id', db.String(64), db.ForeignKey('scene_invitation.id'),
                                        primary_key=True),
                              db.Column('member_card_id', db.String(64), db.ForeignKey('member_cards.id'),
                                        primary_key=True),
                              db.Column('create_at', db.DateTime, default=datetime.datetime.now))


class Permission:
    READER = 0x01
    USER = 0x02
    MEMBER = 0x04
    REGIONAL_AGENT = 0x08
    NATIONAL_AGENT = 0x10
    CUSTOMER_SERVICE = 0x20
    OPERATOR = 0x40
    ADMINISTER = 0x80


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
    elements = db.relationship(
        'Elements',
        secondary=roles_elements,
        backref=db.backref(
            'elements_roles',
            lazy='dynamic'
        )
    )

    def __repr__(self):
        return '<Role %r>' % self.name


class CustomerRoles(db.Model):
    __tablename__ = 'customer_roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    default = db.Column(db.Boolean, default=False, index=True)
    permissions = db.Column(db.Integer)
    customers = db.relationship('Customers', backref='role', lazy='dynamic')

    @staticmethod
    def insert_roles():
        roles = {
            'User': (Permission.READER |
                     Permission.USER, True),
            'Member': (Permission.READER |
                       Permission.USER |
                       Permission.MEMBER, False),
            'REGIONAL_AGENT': (Permission.READER |
                               Permission.USER |
                               Permission.MEMBER |
                               Permission.REGIONAL_AGENT, False),
            'NATIONAL_AGENT': (Permission.READER |
                               Permission.USER |
                               Permission.MEMBER |
                               Permission.REGIONAL_AGENT |
                               Permission.NATIONAL_AGENT, False),
            'OPERATOR': (Permission.READER |
                         Permission.USER |
                         Permission.MEMBER |
                         Permission.REGIONAL_AGENT |
                         Permission.NATIONAL_AGENT |
                         Permission.OPERATOR, False),
            'CUSTOMER_SERVICE': (Permission.CUSTOMER_SERVICE, False),
            'Administrator': (0xff, False)
        }
        for r in roles:
            role = CustomerRoles.query.filter_by(name=r).first()
            if role is None:
                role = CustomerRoles(name=r)
            role.permissions = roles[r][0]
            role.default = roles[r][1]
            db.session.add(role)
        db.session.commit()

    def __repr__(self):
        return '<Role %r>' % self.name


class Elements(db.Model):
    __tablename__ = 'elements'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    icon = db.Column(db.String(50))
    url = db.Column(db.String(250))
    order = db.Column(db.SmallInteger, default=0)
    bg_color = db.Column(db.String(50))
    type = db.Column(db.String(20))
    permission = db.Column(db.String(100), unique=True, index=True, comment='API接口权限')
    parent_id = db.Column(db.Integer, db.ForeignKey('elements.id'))
    parent = db.relationship('Elements', backref="children", remote_side=[id])

    def __repr__(self):
        return '<Element\'s name: %r>' % self.name


class LoginInfo(db.Model):
    __tablename__ = 'login_info'
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(500), nullable=False)
    login_time = db.Column(db.Integer, nullable=False)
    platform = db.Column(db.String(20), nullable=False)
    login_ip = db.Column(db.String(64))
    user = db.Column(db.String(64), db.ForeignKey('users.id'))
    customer = db.Column(db.String(64), db.ForeignKey('customers.id'))
    status = db.Column(db.Boolean, default=True)
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    delete_at = db.Column(db.DateTime)


class PointRecords(db.Model):
    __tablename__ = 'point_records'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    source_type = db.Column(db.SmallInteger, default=1, comment='1: 订单, 提在字典表中，查询point_records获取')
    source_id = db.Column(db.String(64), comment='积分源ID')
    card_id = db.Column(db.String(64), db.ForeignKey('member_cards.id'))
    operation_type = db.Column(db.SmallInteger, default=1, comment='1: 增长， 2: 消费，3: 罚扣')
    points = db.Column(db.Integer, comment='积分数')
    note = db.Column(db.String(100), comment='预留给客服做备注')
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)


class MemberRechargeRecords(db.Model):
    __tablename__ = 'member_recharge_records'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    recharge_amount = db.Column(db.DECIMAL(7, 2), default=0.00, comment="充值金额")
    member_card = db.Column(db.String(64), db.ForeignKey('member_cards.id'))
    note = db.Column(db.String(200), comment='备注')
    usable = db.Column(db.SmallInteger, default=1, comment='0 不可用， 1 可用；例如开通会员卡的金额可设置为不可使用')
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)


class InvitationCode(db.Model):
    """
    邀请码。后台管理员生成邀请码，分配给一级代理商。一级代理商分配给二级的邀请码，也是由后台管理员生成分配给一级代理商
    """
    __tablename__ = 'invitation_code'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    tobe_type = db.Column(db.SmallInteger, comment='邀请后成为的类型，对应member_cards中的member_type')
    tobe_level = db.Column(db.SmallInteger, comment='邀请后成为的等级，对应member_cards中的grade')
    code = db.Column(db.String(64), unique=True, comment='邀请码')
    manager_customer_id = db.Column(db.String(64), db.ForeignKey('customers.id'), comment='管理者ID')
    used_customer_id = db.Column(db.String(64), db.ForeignKey('customers.id'), comment='使用者ID')
    interest_customer_id = db.Column(db.String(64), db.ForeignKey('customers.id'), comment='利益关系ID')
    new_member_card_id = db.Column(db.String(64), db.ForeignKey('member_cards.id'), comment='开卡id')
    creator_id = db.Column(db.String(64), db.ForeignKey('users.id'))
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    validity_at = db.Column(db.DateTime)
    used_at = db.Column(db.DateTime, comment='如果不为空，则表示已经使用，软删除')


class SceneInvitation(db.Model):
    """
    场景邀请码，用于生成一个在一定时间范围内有效的邀请码（二维码）
    """
    __tablename__ = 'scene_invitation'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    name = db.Column(db.String(100), comment='邀请码名称')
    tobe_type = db.Column(db.SmallInteger, comment='邀请后成为的类型，对应member_cards中的member_type')
    tobe_level = db.Column(db.SmallInteger, comment='邀请后成为的等级，对应member_cards中的grade')
    code = db.Column(db.String(64), unique=True, comment='邀请码')
    manager_customer_id = db.Column(db.String(64), db.ForeignKey('customers.id'), comment='管理者ID')
    interest_customer_id = db.Column(db.String(64), db.ForeignKey('customers.id'), comment='利益关系ID')
    invitees = db.relationship(
        'MemberCards',
        secondary=scene_member_cards,
        backref=db.backref(
            'scene_invitation_code'
        )
    )
    max_invitees = db.Column(db.Integer, default=0, comment='最大邀请数, 0表示不限制')
    start_at = db.Column(db.DateTime, comment='有效期开始时间')
    end_at = db.Column(db.DateTime, comment='有效期结束时间')
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)


class MemberCards(db.Model):
    """
    用户登陆小程序后，没有会员卡，获取邀请码之后，可升级为代理商，分别为1级和2级，通过member_type来区分.
    grade来区分登记，1表示一级， 2表示二级。
    普通用户grade目前仅为1
    2020-07-22说明
    """
    __tablename__ = 'member_cards'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    card_no = db.Column(db.String(50), nullable=False, comment='会员卡号')
    member_type = db.Column(db.SmallInteger, default=0, comment='会员类型， 0为普通C端会员； 1 为代理商')
    customer_id = db.Column(db.String(64), db.ForeignKey('customers.id'))
    status = db.Column(db.SmallInteger, default=1, comment='会员卡状态 0: 禁用， 1：正常, 2：挂失')
    grade = db.Column(db.SmallInteger, default=1,
                      comment='会员卡等级，在OptionsDict表中查找card_grades来获取对应的文字描述.默认为1')
    discount = db.Column(db.DECIMAL(3, 2), default=1.00, comment="会员折扣")
    shop_id = db.Column(db.String(64), default='all', comment='预留，对于店铺发店铺会员卡，目前会员卡为商城全局')
    open_date = db.Column(db.DateTime, default=datetime.datetime.now, comment="开卡日期")
    validate_date = db.Column(db.DateTime, comment="卡有效期")
    note = db.Column(db.String(100), comment='备注')
    creator_id = db.Column(db.String(64), db.ForeignKey('users.id'))
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    delete_at = db.Column(db.DateTime, comment='如果不为空，则表示软删除')

    recharge_records = db.relationship('MemberRechargeRecords', backref='cards', lazy='dynamic')


class Scores(db.Model):
    __tablename__ = 'scores'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    customer_id = db.Column(db.String(64), db.ForeignKey('customers.id'))
    reason = db.Column(db.String(64), comment='变更原因')
    quantity = db.Column(db.Integer, comment='积分数值')
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    delete_at = db.Column(db.DateTime)


class Customers(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    phone = db.Column(db.String(15), index=True)
    email = db.Column(db.String(64), index=True)
    openid = db.Column(db.String(64), index=True)
    unionid = db.Column(db.String(64), index=True)
    session_key = db.Column(db.String(64), unique=True, index=True)
    username = db.Column(db.String(64), index=True)
    true_name = db.Column(db.String(30))
    level = db.Column(db.SmallInteger, default=1, comment="用户等级")
    total_points = db.Column(db.Integer, default=0, comment="用户积分")
    total_consumption = db.Column(db.DECIMAL(7, 2), default=0.00, comment='累积消费')
    total_count = db.Column(db.Integer, default=0, comment='累积消费次数')
    role_id = db.Column(db.Integer, db.ForeignKey('customer_roles.id'))
    # 0 unknown, 1 male, 2 female
    gender = db.Column(db.SmallInteger)
    birthday = db.Column(db.Date)
    status = db.Column(db.SmallInteger, comment='1: 正常 0: 删除', default=1)
    address = db.Column(db.String(200))
    login_info = db.relationship('LoginInfo', backref='login_customer', lazy='dynamic')
    orders = db.relationship("ShopOrders", backref='consumer', lazy='dynamic')
    profile_photo = db.Column(db.String(64), comment='微信头像url')
    express_addresses = db.relationship("ExpressAddress", backref='item_sender', lazy='dynamic')
    coupons = db.relationship('CouponReady', backref='receiptor', lazy='dynamic')
    member_card = db.relationship('MemberCards', backref='card_owner', foreign_keys='MemberCards.customer_id',
                                  lazy='dynamic')
    parent_id = db.Column(db.String(64), db.ForeignKey('customers.id'), comment="邀请者，分享小程序入口之后的级联关系写在parent中")
    parent = db.relationship('Customers', backref="children", foreign_keys='Customers.parent_id', remote_side=[id])
    invitor_id = db.Column(db.String(64), db.ForeignKey('customers.id'), comment="代理商邀请")
    invitor = db.relationship('Customers', backref="be_invited", foreign_keys='Customers.invitor_id', remote_side=[id])
    interest_id = db.Column(db.String(64), db.ForeignKey('customers.id'), comment="利益关系")
    interest = db.relationship('Customers', backref="children_market", foreign_keys='Customers.interest_id',
                               remote_side=[id])
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    delete_at = db.Column(db.DateTime)

    invitation_manager = db.relationship('InvitationCode', backref='manager',
                                         foreign_keys='InvitationCode.manager_customer_id',
                                         lazy='dynamic')
    invitation_user = db.relationship('InvitationCode', backref='user',
                                      foreign_keys='InvitationCode.used_customer_id',
                                      lazy='dynamic')
    invitation_interested_user = db.relationship('InvitationCode', backref='interested_customer',
                                                 foreign_keys='InvitationCode.interest_customer_id',
                                                 lazy='dynamic')

    shopping_cart = db.relationship("ShoppingCart", backref='buyer', lazy='dynamic')
    total_cargoes = db.relationship("TotalCargoes", backref='owner', lazy='dynamic')
    refund_orders = db.relationship("Refund", backref='aditor', lazy='dynamic')
    score_changes = db.relationship("Scores", backref='score_owner', lazy='dynamic')

    def __init__(self, **kwargs):
        super(Customers, self).__init__(**kwargs)
        if self.role is None:
            if self.phone == current_app.config['FLASKY_ADMIN']:
                self.role = CustomerRoles.query.filter_by(permissions=0xff).first()
            if self.role is None:
                self.role = CustomerRoles.query.filter_by(default=True).first()

    def verify_code(self, message):
        """
        验证码
        :param message:
        :return:
        """
        login_key = f"front::verification_code::{self.phone}"
        return True if redis_db.exists(login_key) and redis_db.get(login_key) == message else False

    def can(self, permissions):
        return self.role is not None and (self.role.permissions & permissions) == permissions

    @property
    def grade(self):
        member_card = MemberCards.query.filter(MemberCards.customer_id.__eq__(self.id),
                                               MemberCards.member_type.__eq__(1), MemberCards.delete_at.__eq__(None),
                                               MemberCards.status.__eq__(1)).first()

        return member_card.grade if member_card else 0

    def __repr__(self):
        return f"<Customers {self.openid}::{self.phone}>"


class Users(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    phone = db.Column(db.String(15), nullable=False, index=True)
    username = db.Column(db.String(64), index=True)
    email = db.Column(db.String(64), index=True)
    true_name = db.Column(db.String(30))
    birthday = db.Column(db.Date)
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
    address = db.Column(db.String(200))
    login_info = db.relationship('LoginInfo', backref='login_user', lazy='dynamic')
    member_card = db.relationship('MemberCards', backref='cards_creator', lazy='dynamic')
    invitation = db.relationship('InvitationCode', backref='creator', lazy='dynamic')
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    delete_at = db.Column(db.DateTime)

    @property
    def permissions(self):
        return Elements.query.outerjoin(roles_elements).outerjoin(Roles).outerjoin(user_role).outerjoin(Users). \
            filter(Users.id == self.id, Elements.permission is not None).order_by(Elements.order).all()

    @property
    def elements(self):
        return Elements.query.outerjoin(roles_elements).outerjoin(Roles).outerjoin(user_role).outerjoin(Users). \
            filter(
            Users.id == self.id,
            Elements.type != 'api'
        ).order_by(Elements.order).all()

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def verify_code(self, message):
        """
        验证码
        :param message:
        :return:
        """
        login_key = f"back::verification_code::{self.phone}"
        return True if redis_db.exists(login_key) and redis_db.get(login_key) == message else False

    def __repr__(self):
        return '<User %r>' % self.username


class Countries(db.Model):
    __tablename__ = 'countries'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, index=True, nullable=False)
    longitude = db.Column(db.String(20))
    latitude = db.Column(db.String(20))
    population = db.Column(db.Integer)
    provinces = db.relationship("Provinces", backref="countries", lazy='dynamic')


class Provinces(db.Model):
    __tablename__ = 'provinces'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, index=True, nullable=False)
    longitude = db.Column(db.String(20))
    latitude = db.Column(db.String(20))
    population = db.Column(db.Integer)
    country_id = db.Column(db.Integer, db.ForeignKey('countries.id'))
    cities = db.relationship("Cities", backref='provinces', lazy='dynamic')


class Cities(db.Model):
    __tablename__ = 'cities'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, index=True, nullable=False)
    longitude = db.Column(db.String(20))
    latitude = db.Column(db.String(20))
    population = db.Column(db.Integer)
    province_id = db.Column(db.Integer, db.ForeignKey('provinces.id'))
    districts = db.relationship("Districts", backref='included_cities', lazy='dynamic')
    express_address = db.relationship("ExpressAddress", backref='buyer_cities', lazy='dynamic')


class Districts(db.Model):
    __tablename__ = 'districts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, index=True, nullable=False)
    longitude = db.Column(db.String(20))
    latitude = db.Column(db.String(20))
    population = db.Column(db.Integer)
    city_id = db.Column(db.Integer, db.ForeignKey('cities.id'))
    express_address = db.relation("ExpressAddress", backref='buyer_district', lazy='dynamic')


class Brands(db.Model):
    __tablename__ = 'brands'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    name = db.Column(db.String(100), nullable=False, index=True)
    logo = db.Column(db.String(64), db.ForeignKey('obj_storage.id'))
    company_name = db.Column(db.String(100))
    company_address = db.Column(db.String(100))
    spu = db.relationship('SPU', backref='brand', lazy='dynamic')


class Classifies(db.Model):
    __tablename__ = 'classifies'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    name = db.Column(db.String(50), nullable=False)
    spu = db.relationship('SPU', backref='classifies', lazy='dynamic')


class Standards(db.Model):
    __tablename__ = 'standards'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    name = db.Column(db.String(50), nullable=False, unique=True, index=True)
    values = db.relationship('StandardValue', backref='standards', lazy='dynamic')


class StandardValue(db.Model):
    __tablename__ = 'standard_value'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    standard_id = db.Column(db.String(64), db.ForeignKey('standards.id'))
    value = db.Column(db.String(50), nullable=False, unique=True, index=True)


class SPU(db.Model):
    __tablename__ = 'spu'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    name = db.Column(db.String(100), nullable=False, index=True)
    sub_name = db.Column(db.String(100))
    express_fee = db.Column(db.DECIMAL(6, 2), default=0.00, comment="邮费，默认0元")
    contents = db.Column(db.Text(length=(2 ** 32) - 1))
    standards = db.relationship(
        'Standards',
        secondary=spu_standards,
        backref=db.backref(
            'spu'
        )
    )
    objects = db.relationship(
        'ObjStorage',
        secondary=spu_obj,
        backref=db.backref('obj_spu')
    )
    brand_id = db.Column(db.String(64), db.ForeignKey('brands.id'))
    classify_id = db.Column(db.String(64), db.ForeignKey('classifies.id'))
    sku = db.relationship('SKU', backref='the_spu', lazy='dynamic')
    status = db.Column(db.SmallInteger, default=0, comment="1 上架； 0 下架")
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    delete_at = db.Column(db.DateTime)


class PurchaseInfo(db.Model):
    __tablename__ = 'purchase_info'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    sku_id = db.Column(db.String(64), db.ForeignKey('sku.id'))
    amount = db.Column(db.Integer)
    operator = db.Column(db.String(64))
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    status = db.Column(db.SmallInteger, default=1, comment="1 正常 0 作废")
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    memo = db.Column(db.String(200), comment="备忘，例如作废原因")


class WareHouse(db.Model):
    __tablename__ = 'warehouse'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    name = db.Column(db.String(64))
    address = db.Column(db.String(100))
    purpose = db.Column(db.String(100), comment='仓库用途')
    status = db.Column(db.SmallInteger, default=1, comment='仓库状态，默认1为在用')
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    delete_at = db.Column(db.DateTime)
    total_cargoes = db.relationship("TotalCargoes", backref='cargo_warehous', lazy='dynamic')


class PackingItemOrders(db.Model):
    __tablename__ = 'packing_item_orders'
    # 当进入分装流程时，先生成一个分装的订单，如果
    id = db.Column(db.String(64), primary_key=True, default=make_order_id)
    total_cargoes_id = db.Column(db.String(64), db.ForeignKey('total_cargoes.id'))
    shop_order_id = db.Column(db.String(64), db.ForeignKey('shop_orders.id'), comment='分装的总订单')
    materials_in_cart = db.relationship('ShoppingCart', backref='packing_order', lazy='dynamic')
    consumption = db.Column(db.DECIMAL(7, 2), comment='总量中分装的消耗量，单位与total_cargoes中的unit相同')
    loss = db.Column(db.DECIMAL(7, 2), default=0.00, comment='分装过程的损耗，默认为0.00')
    create_at = db.Column(db.DateTime, default=datetime.datetime.now, comment='创建分装的日期')
    # 支付时间看对应的订单
    packing_at = db.Column(db.String(64), comment='选择完所有材料后提交结算的时间')
    pay_at = db.Column(db.DateTime,
                       comment='支付完成回调时，如果是shop_orders中外键关联packing_order不为空，那么就update这个parcking_order中的pay_at，表示支付完成')
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    # 如果delete_at不为空，表示此分装订单没有生效
    delete_at = db.Column(db.DateTime)


class TotalCargoes(db.Model):
    __tablename__ = 'total_cargoes'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    cargo_code = db.Column(db.String(64), comment='货物编号')
    warehouse_id = db.Column(db.String(64), db.ForeignKey('warehouse.id'), comment='货物存储房间')
    cargo_pan = db.Column(db.String(3), comment='货物水平位置')
    cargo_tilt = db.Column(db.String(3), comment='货物垂直位置')
    cargo_zoom = db.Column(db.String(3), comment='货物焦距位置')
    order_id = db.Column(db.String(64), db.ForeignKey('shop_orders.id'), comment='外键关联订单')
    storage_date = db.Column(db.DateTime)
    init_total = db.Column(db.DECIMAL(7, 2), comment='初始的总量')
    last_total = db.Column(db.DECIMAL(7, 2), comment='最后的总量')
    unit = db.Column(db.String(10), default='斤', comment='货物单位')
    key_code = db.Column(db.String(100), comment='智能锁远程访问id')
    key_pwd = db.Column(db.String(100), comment='key 密钥')
    # 存放封坛相关的照片，后续还能上传
    cargo_media = db.relationship(
        'ObjStorage',
        secondary=cargo_obj,
        backref=db.backref('obj_cargo')
    )
    packing_orders = db.relationship('PackingItemOrders', backref='parent_cargo', lazy='dynamic')
    owner_name = db.Column(db.String(20), comment='货物主人姓名')
    owner_id = db.Column(db.String(64), db.ForeignKey('customers.id'))
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    delete_at = db.Column(db.DateTime)


class SKU(db.Model):
    __tablename__ = 'sku'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    name = db.Column(db.String(100), nullable=False, index=True)
    show_price = db.Column(db.String(13), default='0.00', comment='显示价格， 当special不为0时，显示此价格，并且用删除线')
    price = db.Column(db.DECIMAL(10, 2), default=0.00)
    seckill_price = db.Column(db.DECIMAL(10, 2), default=0.00, comment='当SKU参加秒杀活动时，设置秒杀价格写在这个字段，如果不为0， 则表示参加秒杀，查找秒杀活动')
    discount = db.Column(db.DECIMAL(3, 2), default=1.00)
    member_price = db.Column(db.DECIMAL(10, 2), default=0.00)
    score_type = db.Column(db.SmallInteger, default=0, comment='是否可用积分')
    get_score = db.Column(db.Integer, comment="可以获得的积分")
    max_score = db.Column(db.Integer, comment='最多可用积分')
    contents = db.Column(db.Text(length=(2 ** 32) - 1), comment='富文本，sku描述')
    quantity = db.Column(db.Integer, default=0, index=True)
    spu_id = db.Column(db.String(64), db.ForeignKey('spu.id'))
    unit = db.Column(db.String(6), nullable=False)
    special = db.Column(db.SmallInteger, default=0,
                        comment="0 非特价商品，1 特价商品， 2 赠品，不可单独销售, 30 ~ 69: 表示有后续业务流程的商品，当前用31，表示分装所需包装材料，订单生成后，会产生分装订单")
    need_express = db.Column(db.SmallInteger, default=1, comment="1: 可快递， 0: 不可快递")
    express_fee = db.Column(db.DECIMAL(7, 2), default=10.00, comment='sku 默认快递费')
    per_user = db.Column(db.SmallInteger, default=0, comment="设置限购量，默认为0不限购，一般在特价，秒杀折扣时使用")
    values = db.relationship(
        'StandardValue',
        secondary=sku_standardvalue,
        backref=db.backref('sku')
    )
    objects = db.relationship(
        'ObjStorage',
        secondary=sku_obj,
        backref=db.backref('obj_sku')
    )
    rebates_id = db.Column(db.String(64), db.ForeignKey("rebates.id"))
    status = db.Column(db.SmallInteger, default=0, comment="1 上架； 0 下架")
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    delete_at = db.Column(db.DateTime)
    could_get_coupon_id = db.Column(db.String(64), db.ForeignKey('coupons.id'), comment='如果是直客，那么可以设置获取优惠券')
    order = db.relationship(
        'ShopOrders',
        secondary=sku_shoporders,
        backref=db.backref('order_sku')
    )
    purchase_info = db.relationship('PurchaseInfo', backref='purchase_sku', lazy='dynamic')
    sku_layout = db.relationship('SKULayout', backref='layout_sku', lazy='dynamic')
    shopping_cart = db.relationship('ShoppingCart', backref='desire_skus', lazy='dynamic')
    sku_orders = db.relationship("ItemsOrders", backref='bought_sku', lazy='dynamic')


class PersonalRebates(db.Model):
    """
    个人返佣表。 支付成功后，吊起返佣计算流程
    """
    __tablename__ = 'personal_rebates'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    shop_order_id = db.Column(db.String(64), db.ForeignKey('shop_orders.id'))
    customer_id = db.Column(db.String(64), db.ForeignKey('customers.id'))
    rebate = db.Column(db.DECIMAL(5, 2), comment='支付成功时该账户应得的返佣比例')
    rebate_value = db.Column(db.DECIMAL(9, 2), comment='返佣金额')
    score = db.Column(db.SmallInteger, default=0, comment='获赠的积分')
    status = db.Column(db.SmallInteger, default=0, comment='0: 不可提现（刚购买或者用户提出退货后） 1：可提现 2：已提现')
    # 创建日期过一定天数后才能体现
    relation = db.Column(db.String(20), comment='返佣关系')
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    delete_at = db.Column(db.DateTime)


class Rebates(db.Model):
    """
    invitor 指提供邀请码的用户，可以是公司市场部，也可以是一级代理。 邀请码都由后台统一生成
    parent 用来关联分享链接的上下级关系，用来锁定上下级；
    例如：
    1. 一级代理A 分享给未使用过商城的B， B成为商城的直客，成为A的下游，所有B的消费，A提成30%
    2. A某日说服B成为二级代理，A提供B升级邀请码，B成为二级后，A获取B销售额的10%
    3. B 某日想成为一级代理，A向总公司申请一级代理邀请码，分配给B，B的销售提成和A脱钩， A获取一次性费用3万元。此处预留，以后可能不脱钩，留1%的提成
    4. A的直客封坛，A返佣10%； B（二级）的用户或者自己封坛，B返佣10%， A也同样有销售额的10%提成（符合销售管理奖金10%的规则）
    5. B某日发展了用户C为二级， B提成C的销售额的5%， A也同样提成C的销售额的5% 。 C的提成政策按照二级代理计算
    6. C某日发展了用户D为二级， C提成D的销售额的5%， B没有提成，A提成D的销售额的5% 。
    7. B邀请C，C邀请D的邀请码，平台默认给每个二级代理10个二级代理邀请码
    8. B某日邀请用户E为一级， B或者E 直接咨询客户，客户联系对接E，进行沟通审核后分配一级代理邀请码 成功后B获取一次性佣金3万元
    9. 总部路演等方式，招的一级代理，或者二级代理，都挂在市场部账号下。市场部账号为一级代理。市场部拓展的渠道始终由市场部管理。
    10. 二级代理自己消费，或者其下游直客消费，提成20%， 封坛佣金10% 。
    11. 直客也可邀请用户成为二级或者一级，直接找自己上级或者客服咨询
    12. 关于邀请码的规则，一级代理商邀请码都由总部市场部发出； 二级邀请码，代理商都可以发，默认给10个，不够了找客服申请
    """
    __tablename__ = 'rebates'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    name = db.Column(db.String(64), comment="用来命名返佣表名称")
    c_to_c_bonus_score = db.Column(db.DECIMAL(5, 2), comment='c to c 可获取的奖励积分, 这里的百分比是消费额的百分比作为积分, 从parent_id来查找')
    agent_second_rebate = db.Column(db.DECIMAL(5, 2), default=20.00, comment='填写百分比，譬如20.00, 表示返佣20%')
    agent_first_rebate = db.Column(db.DECIMAL(5, 2), default=30.00, comment='填写百分比，譬如30.00, 表示返佣30%')
    agent_second_invitor_rebate = db.Column(db.DECIMAL(5, 2), default=5.00, comment='填写百分比，譬如5.00, 表示返佣5%')
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    sku = db.relationship("SKU", backref='rebate', lazy='dynamic')


class Coupons(db.Model):
    __tablename__ = 'coupons'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    name = db.Column(db.String(64), nullable=False, comment="优惠券标题")
    desc = db.Column(db.String(100), comment='优惠券描述')
    icon = db.Column(db.String(64), db.ForeignKey('obj_storage.id'), comment="优惠券图标")
    quota = db.Column(db.Integer, default=1, comment='配额：发券数量')
    per_user = db.Column(db.SmallInteger, default=1, comment='每用户允许领取数量')
    take_count = db.Column(db.Integer, default=0, comment='已领取的优惠券数量')
    used_count = db.Column(db.Integer, default=0, comment='已使用的优惠券数量')
    valid_type = db.Column(db.SmallInteger, default=2, comment='时效:1绝对时效（领取后XXX-XXX时间段有效）  2相对时效（领取后N天有效）')
    valid_days = db.Column(db.Integer, default=1, comment='自领取之日起有效天数')
    absolute_date = db.Column(db.DateTime, comment='优惠券的绝对结束日期，当valid_type为1时，此项不能为空')
    status = db.Column(db.SmallInteger, comment='1生效 2失效 3已结束', default=1)
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    coupon_sent = db.relationship("CouponReady", backref='coupon_setting', lazy='dynamic')
    promotions = db.relationship("Promotions", backref='coupons', lazy='dynamic')
    skus = db.relationship("SKU", backref='could_get_coupon', lazy='dynamic')


class CouponReady(db.Model):
    __tablename__ = 'coupon_ready'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    coupon_id = db.Column(db.String(64), db.ForeignKey('coupons.id'))
    status = db.Column(db.SmallInteger, default=1, comment="0: 作废，1：已领取未使用，2：已使用")
    take_at = db.Column(db.DateTime, default=datetime.datetime.now)
    use_at = db.Column(db.DateTime)
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    consumer = db.Column(db.String(64), db.ForeignKey('customers.id'))


class ShopOrders(db.Model):
    __tablename__ = 'shop_orders'
    id = db.Column(db.String(64), primary_key=True, default=make_order_id)
    customer_id = db.Column(db.String(64), db.ForeignKey('customers.id'))
    transaction_id = db.Column(db.String(64), comment="微信支付的订单号，回调中获取")
    items_total_price = db.Column(db.DECIMAL(10, 2), default=0.00, comment='未使用积分的总价')
    score_used = db.Column(db.Integer, default=0, comment="使用的积分")
    is_pay = db.Column(db.SmallInteger, default=0, comment="默认0. 0：未支付， 1：完成支付， 2：支付失败, 3:支付中")
    pay_err_code = db.Column(db.String(32), comment="微信支付回调结果，如果有错误")
    pay_err_code_des = db.Column(db.String(128), comment="微信支付回调结果描述")
    bank_type = db.Column(db.String(32), comment="回调用户的银行类型，如果成功")
    pre_pay_time = db.Column(db.DateTime, comment='后台支付获取预付ID成功时间')
    pay_time = db.Column(db.DateTime, comment="支付成功时间")
    cash_fee = db.Column(db.DECIMAL(10, 2), comment="微信支付实际现金支付金额")
    is_ship = db.Column(db.SmallInteger, default=0, comment="0：未发货，1：已发货")
    ship_time = db.Column(db.DateTime, comment="发货时间")
    receive_time = db.Column(db.DateTime, comment="收货时间")
    is_receipt = db.Column(db.SmallInteger, default=0, comment="0：未发货 1：已发货未签收 2：已发货已签收")
    express_company = db.Column(db.String(50), comment='快递公司')
    express_number = db.Column(db.String(50), comment='快递号')
    express_fee = db.Column(db.DECIMAL(7, 2), default=0.00)
    express_address = db.Column(db.String(200), comment="记录下单时发货地址，防止地址记录修改。 原express_address表中address1+address2")
    express_postcode = db.Column(db.String(7), comment='邮编')
    express_recipient = db.Column(db.String(20), comment='收件人')
    express_recipient_phone = db.Column(db.String(13), comment='收件人手机号')
    status = db.Column(db.SmallInteger, default=1,
                       comment="1：正常 2：禁用 0：订单取消(delete_at 写入时间)")
    items_orders_id = db.relationship("ItemsOrders", backref='shop_orders', lazy='dynamic')
    total_cargoes = db.relationship("TotalCargoes", backref='cargo_order', lazy='dynamic')
    packing_order = db.relationship("PackingItemOrders", backref='packing_item_order', lazy='dynamic')
    message = db.Column(db.String(500), comment='用户留言')
    cancel_reason = db.Column(db.String(64), comment='取消原因，给用户下拉选择')
    invoice_type = db.Column(db.SmallInteger, default=0, comment="0: 个人 1: 企业")
    invoice_title = db.Column(db.String(100), comment='发票抬头，如果type是0，则此处为个人')
    invoice_tax_no = db.Column(db.String(20), comment='企业税号')
    inovice_email = db.Column(db.String(50), comment='发票发送邮箱')
    rebate_records = db.relationship('PersonalRebates', backref='related_order', lazy='dynamic')
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    delete_at = db.Column(db.DateTime)


class ItemsOrders(db.Model):
    __tablename__ = 'items_orders'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    order_id = db.Column(db.String(64), db.ForeignKey('shop_orders.id'))
    item_id = db.Column(db.String(64), db.ForeignKey('sku.id'))
    item_quantity = db.Column(db.Integer, default=1)
    item_price = db.Column(db.DECIMAL(10, 2), comment="下单时sku的价格，如果有show_price，记录show_price，否则记录price")
    transaction_price = db.Column(db.DECIMAL(10, 2), comment="实际交易的价格，未使用积分的价格，例如有会员价，有折扣（real_price）")
    benefits = db.relationship(
        'Benefits',
        secondary=itemsorders_benefits,
        backref=db.backref('item_orders')
    )
    status = db.Column(db.SmallInteger, default=0, comment='1：正常 2：禁用 0：订单未完成 3:退货中，4: 退货成功')
    special = db.Column(db.SmallInteger, default=0, comment='0.默认正常商品；1.有仓储分装流程的商品')
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, default=datetime.datetime.now)
    delete_at = db.Column(db.DateTime)
    rates = db.Column(db.String(64), db.ForeignKey('evaluates.id'), comment='评分')
    refund_order = db.relationship("Refund", backref='item_orders', lazy='dynamic')


class ExpressAddress(db.Model):
    __tablename__ = 'express_address'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    sender = db.Column(db.String(64), db.ForeignKey('customers.id'))
    city_id = db.Column(db.Integer, db.ForeignKey('cities.id'), comment="目前不用，后续拆分地址后存放城市id")
    district = db.Column(db.Integer, db.ForeignKey('districts.id'), comment="目前不用，后续拆分地址后存放区id")
    address1 = db.Column(db.String(100), comment="某某路xx号xx栋xx门牌号")
    address2 = db.Column(db.String(100))
    postcode = db.Column(db.String(10), comment="邮编")
    recipient = db.Column(db.String(50), comment="收件人")
    recipient_phone = db.Column(db.String(20), comment="收件人电话")
    status = db.Column(db.SmallInteger, default=1, comment="1：正常 0：删除")
    is_default = db.Column(db.Boolean, default=False)


class Evaluates(db.Model):
    __tablename__ = 'evaluates'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    express_rate = db.Column(db.SmallInteger, default=10, comment="物流评价0~10")
    item_rate = db.Column(db.SmallInteger, default=10, comment="商品评价0~10")
    content = db.Column(db.Text(length=(2 ** 32) - 1))
    used_pic = db.Column(db.String(64), db.ForeignKey('obj_storage.id'))
    item_order = db.relationship('ItemsOrders', backref='evaluates', lazy='dynamic')


class Layout(db.Model):
    __tablename__ = 'layout'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, comment="页面板块名称")
    desc = db.Column(db.String(100), comment="描述、备注")
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    layout_sku = db.relationship('SKULayout', backref='layout', lazy='dynamic')


class SKULayout(db.Model):
    __tablename__ = 'sku_layout'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    layout_id = db.Column(db.Integer, db.ForeignKey('layout.id'))
    sku_id = db.Column(db.String(64), db.ForeignKey('sku.id'), nullable=False)
    order = db.Column(db.Integer, default=1, comment="排序")
    status = db.Column(db.SmallInteger, default=1, comment='0 禁用 1 正常')
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)


class SMSTemplate(db.Model):
    __tablename__ = 'sms_template'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    template_id = db.Column(db.String(64), nullable=False)
    platform = db.Column(db.String(100), default='tencent', nullable=False)
    content = db.Column(db.String(140))
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)


class SMSSign(db.Model):
    __tablename__ = 'sms_sign'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    sign_id = db.Column(db.String(64), nullable=False)
    content = db.Column(db.String(140))
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)


class SMSApp(db.Model):
    __tablename__ = 'sms_app'
    id = db.Column(db.Integer, primary_key=True)
    app_id = db.Column(db.String(64), nullable=False, index=True)
    app_key = db.Column(db.String(64), nullable=False, index=True)
    platform = db.Column(db.String(100), default='tencent', nullable=False)
    status = db.Column(db.SmallInteger, default=1, comment="1正常；2暂停")
    callback_url = db.Column(db.String(100), comment="短信回调URL")
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)


class PromotionGroups(db.Model):
    """设置促销活动组"""
    __tablename__ = 'promotion_groups'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    group_id = db.Column(db.SmallInteger, comment="组ID， 0 为特殊组，特殊组和任何组不互斥")
    priority = db.Column(db.SmallInteger, unique=True, comment="优先级不可重复，用于排序")
    name = db.Column(db.String(30))
    desc = db.Column(db.String(100))
    promotions = db.relationship('Promotions', backref='groups', lazy='dynamic')
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)


class Gifts(db.Model):
    """折扣商品或者赠品表"""
    __tablename__ = 'gifts'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    sku = db.Column(db.String(64), db.ForeignKey('sku.id'))
    discount = db.Column(db.DECIMAL(3, 2), default=0.00, comment='如果是0折，则为赠送，其它折扣，则为降价商品')
    benefit = db.Column(db.String(64), db.ForeignKey('benefits.id'))
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)


class Benefits(db.Model):
    """活动利益表"""
    __tablename__ = 'benefits'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    name = db.Column(db.String(64))
    with_amount = db.Column(db.Integer, default=0, comment="满多少金额")
    reduced_amount = db.Column(db.Integer, default=0, comment="满xx后减多少钱，只能是整数")
    discount_amount = db.Column(db.DECIMAL(3, 2), default=1.00, comment='满xx后的折扣')
    with_quantity = db.Column(db.Integer, default=0, comment="满多少件")
    free_quantity = db.Column(db.SmallInteger, default=0, comment="满xx送几件")
    pay_more = db.Column(db.DECIMAL(10, 2), default=0.00, comment='加价购，可选范围在gifts中，由pay_more_quantity来控制加价购可选商品数量')
    pay_more_quantity = db.Column(db.SmallInteger, comment='控制加价购数量')
    combo_price = db.Column(db.DECIMAL(10, 2), default=0.00, comment='仅当活动类型是4时生效, 添加的sku为活动范围，添加的gifts为这个sku套餐的其它sku')
    combo_express_fee = db.Column(db.DECIMAL(7, 2), default=0.00, comment='套餐的快递价格，例如药酒封坛，则为0')
    presell_price = db.Column(db.DECIMAL(10, 2), default=0.00, comment='当类型是5时， 设置预售定金')
    presell_multiple = db.Column(db.DECIMAL(3, 2), default=0.00, comment='预售定金倍数，例如定金是10元，倍数是1.5，那么抵扣商品15元')
    gifts = db.relationship('Gifts', secondary=benefits_gifts, backref=db.backref('benefits'))
    status = db.Column(db.SmallInteger, comment='1生效 2失效 3已结束', default=1)
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    shopping_cart = db.relationship("ShoppingCart", backref='combo_benefit', lazy='dynamic')


class Promotions(db.Model):
    """
    用于设置活动规则
    """
    __tablename__ = 'promotions'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    name = db.Column(db.String(64), comment="促销活动名称", unique=True, index=True)
    first_order = db.Column(db.SmallInteger, default=0, comment='0: 不是首单，1: 首单, 用户首单参加活动')
    reject_coupon = db.Column(db.SmallInteger, default=0, comment='是否排斥优惠券，默认0不排斥，1排斥')
    customer_level = db.Column(db.SmallInteger, default=1, comment='用户等级，1为最低')
    gender = db.Column(db.SmallInteger, default=0, comment='参与的性别，默认为0， 1为男性、2为女性')
    age_min = db.Column(db.SmallInteger, default=0, comment='参与最小年龄，默认为0')
    age_max = db.Column(db.SmallInteger, default=200, comment='参与最大年龄，默认为200')
    promotion_type = db.Column(db.SmallInteger, comment='0: 满减，1：满赠，2：满折，3：加价购，4：套餐，5：预售, 6：秒杀, 7: 满减优惠券, 8: 满赠优惠券')

    express_free = db.Column(db.SmallInteger, default=0, comment="0: 不包邮, 1: 包邮")

    accumulation = db.Column(db.SmallInteger, default=0, comment='是否允许累积，默认为0，不允许。如果允许累加则为1。如果可以累加，则利益规则数量会大于')
    scope = db.Column(db.SmallInteger, default=1, comment='0：非全场，1: 全场， 2：线下')

    # 多对多关系
    brands = db.relationship('Brands', secondary=promotions_brands, backref=db.backref('brand_promotions'))
    spu = db.relationship('SPU', secondary=promotions_spu, backref=db.backref('spu_promotions'))
    sku = db.relationship('SKU', secondary=promotions_sku, backref=db.backref('sku_promotions'))
    classifies = db.relationship('Classifies',
                                 secondary=promotions_classifies,
                                 backref=db.backref('classifies_promotions'))
    benefits = db.relationship('Benefits', secondary=promotions_benefits, backref=db.backref('benefits_promotions'))
    group = db.Column(db.String(64), db.ForeignKey('promotion_groups.id'), comment='group_id 为-1表示是发优惠券，>=0的group，为活动')

    with_special = db.Column(db.SmallInteger, default=0, comment="1: 可用于特价商品 0: 不能。默认不能(商品优惠卷除外)")
    start_time = db.Column(db.DateTime, comment='活动开始时间')
    end_time = db.Column(db.DateTime, comment='活动结束时间')
    status = db.Column(db.SmallInteger, comment='1生效 2失效 3已结束', default=1)
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    coupon_id = db.Column(db.String(64), db.ForeignKey('coupons.id'))

    def __repr__(self):
        return '<Promotion name %r>' % self.name


class Banners(db.Model):
    """
    Banners内容存储
    """
    __tablename__ = 'banners'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    name = db.Column(db.String(64), index=True, nullable=False, comment="banner的名称")
    order = db.Column(db.SmallInteger, default=0, comment="排序，若相同则无序")
    objects = db.Column(db.String(64), db.ForeignKey('obj_storage.id'))
    url = db.Column(db.String(200), comment="用于存放点击后跳转的链接")
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)


class ObjStorage(db.Model):
    """
    存放对象存储的结果
    """
    __tablename__ = 'obj_storage'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    bucket = db.Column(db.String(64), nullable=False, index=True)
    region = db.Column(db.String(64), nullable=False, index=True)
    obj_key = db.Column(db.String(64), nullable=False, index=True)
    obj_type = db.Column(db.SmallInteger, default=0, comment="0 图片，1 视频， 2 文本")
    url = db.Column(db.String(150), nullable=False, index=True)
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    parent_id = db.Column(db.String(64), db.ForeignKey('obj_storage.id'))
    parent = db.relationship('ObjStorage', backref="thumbnails", remote_side=[id])

    banners = db.relationship('Banners', backref='banner_contents', lazy='dynamic')
    coupons = db.relationship('Coupons', backref="icon_objects", lazy='dynamic')
    evaluates = db.relationship("Evaluates", backref="experience_objects", lazy='dynamic')
    brands = db.relationship('Brands', backref='logo_objects', lazy='dynamic')
    # customers = db.relationship('Customers', backref='photo_objects', lazy='dynamic')
    news_center = db.relationship('NewsCenter', backref='news_cover_image', lazy='dynamic')


class ShoppingCart(db.Model):
    """
    用户购物车，用于存放用户的购物车清单，只存放sku的快照，图片，价格。若实际SKU删除（软删除）或者下架，则前端页面显示此商品已失效
    """
    __tablename__ = 'shopping_cart'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    customer_id = db.Column(db.String(64), db.ForeignKey('customers.id'))
    sku_id = db.Column(db.String(64), db.ForeignKey('sku.id'))
    quantity = db.Column(db.SmallInteger, default=1, comment="购买的数量")
    combo = db.Column(db.String(64), db.ForeignKey('benefits.id'),
                      comment='前端页面选择的combo，实质为这个套餐中的一种，为benefits表的id')
    status = db.Column(db.SmallInteger, default=1, comment='预留，默认为1，则显示在购物车中，如果为0， 则作为想买货物，不在购物车内')
    packing_item_order = db.Column(db.String(64), db.ForeignKey('packing_item_orders.id'))
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    delete_at = db.Column(db.DateTime)


class NewsSections(db.Model):
    """
    新闻栏目
    """
    __tablename__ = 'news_sections'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    name = db.Column(db.String(64))
    section_image = db.Column(db.String(64), db.ForeignKey('obj_storage.id'))
    order = db.Column(db.SmallInteger, default=0, comment='栏目排序')
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    delete_at = db.Column(db.DateTime)
    news = db.relationship('NewsCenter', backref='news_section', lazy='dynamic')


class NewsCenter(db.Model):
    """
    咨询类
    """
    __tablename__ = 'news_center'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    title = db.Column(db.String(30), comment="主标题")
    sub_title = db.Column(db.String(30), comment="副标题")
    cover_image = db.Column(db.String(64), db.ForeignKey('obj_storage.id'))
    content = db.Column(db.Text(length=(2 ** 32) - 1), comment='富文本，sku描述')
    order = db.Column(db.SmallInteger, default=0, comment='文章排序')
    news_section_id = db.Column(db.String(64), db.ForeignKey('news_sections.id'))
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    delete_at = db.Column(db.DateTime)


class Refund(db.Model):
    """
    退货申请单
    """
    __tablename__ = 'refund'
    id = db.Column(db.String(64), primary_key=True, default=make_uuid)
    refund_quantity = db.Column(db.SmallInteger, comment='退货数量')
    refund_reason = db.Column(db.String(64), comment='退货原因')
    refund_desc = db.Column(db.String(200), comment='问题描述')
    collect_addr = db.Column(db.String(200), comment='取件地址')
    status = db.Column(db.SmallInteger, default=0, comment='0: 审核中，1: 审核成功，2：审核失败')
    audit_result = db.Column(db.String(200), comment="审核结果描述")
    auditor = db.Column(db.String(64), db.ForeignKey('customers.id'))
    express_no = db.Column(db.String(100), comment='快递单号')
    item_order_id = db.Column(db.String(64), db.ForeignKey('items_orders.id'))
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    delete_at = db.Column(db.DateTime)


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

# 支付成功后，7天内可退货
RETURN_IN_DAYS = 7
# 在过了退货期之后+3天可提现
REBATE_TO_CASH = 3

NEW_ONE_SCORES = 88
SHARE_AWARD = 88
