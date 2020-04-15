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

elements_permissions = db.Table('elements_permissions',
                                db.Column('element_id', db.Integer, db.ForeignKey('elements.id'), primary_key=True),
                                db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id'),
                                          primary_key=True),
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

sku_img = db.Table('sku_img',
                   db.Column('sku_id', db.String(64), db.ForeignKey('sku.id'), primary_key=True),
                   db.Column('img_id', db.String(64), db.ForeignKey('img_url.id'), primary_key=True),
                   db.Column('create_at', db.DateTime, default=datetime.datetime.now))

sku_shoporders = db.Table('sku_shoporders',
                          db.Column('sku_id', db.String(64), db.ForeignKey('sku.id'), primary_key=True),
                          db.Column('shoporders_id', db.String(64), db.ForeignKey('shop_orders.id'), primary_key=True),
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


class Elements(db.Model):
    __tablename__ = 'elements'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    icon = db.Column(db.String(50))
    url = db.Column(db.String(250))
    order = db.Column(db.SmallInteger, default=0)
    bg_color = db.Column(db.String(50))
    type = db.Column(db.String(20))
    permissions = db.relationship(
        'Permissions',
        secondary=elements_permissions,
        backref=db.backref(
            'permissions_elements',
            lazy='dynamic'
        )
    )
    parent_id = db.Column(db.Integer, db.ForeignKey('elements.id'))
    parent = db.relationship('Elements', backref="children", remote_side=[id])

    def __repr__(self):
        return '<Element\'s name: %r>' % self.name


class Permissions(db.Model):
    __tablename__ = 'permissions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), index=True)
    action = db.Column(db.String(250), unique=True, index=True)


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


class PointRecords(db.Model):
    __tablename__ = 'point_records'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
    source_type = db.Column(db.SmallInteger, default=1, comment='1: 订单, 提在字典表中，查询point_records获取')
    source_id = db.Column(db.String(64), comment='积分源ID')
    card_id = db.Column(db.String(64), db.ForeignKey('member_cards.id'))
    operation_type = db.Column(db.SmallInteger, default=1, comment='1: 增长， 2: 消费，3: 罚扣')
    points = db.Column(db.Integer, comment='积分数')
    note = db.Column(db.String(100), comment='预留给客服做备注')
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)


class MemberRechargeRecords(db.Model):
    __tablename__ = 'member_recharge_records'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
    recharge_amount = db.Column(db.DECIMAL(7, 2), default=0.00, comment="充值金额")


class MemberCards(db.Model):
    __tablename__ = 'member_cards'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
    card_no = db.Column(db.String(50), nullable=False, comment='会员卡号')
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


class Customers(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
    phone = db.Column(db.String(15), nullable=False, index=True)
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

    # 0 unknown, 1 male, 2 female
    gender = db.Column(db.SmallInteger)
    birthday = db.Column(db.Date)
    roles = db.relationship(
        'Roles',
        secondary=customer_role,
        backref=db.backref(
            'customers'
        )
    )
    password_hash = db.Column(db.String(128))
    status = db.Column(db.SmallInteger, comment='1: 正常 0: 删除')
    address = db.Column(db.String(200))
    login_info = db.relationship('LoginInfo', backref='login_customer', lazy='dynamic')
    orders = db.relationship("ShopOrders", backref='consumer', lazy='dynamic')
    profile_photo = db.Column(db.String(64), db.ForeignKey('img_url.id'))
    express_addresses = db.relationship("ExpressAddress", backref='item_sender', lazy='dynamic')
    coupons = db.relationship('CouponReady', backref='receiptor', lazy='dynamic')
    member_card = db.relationship('MemberCards', backref='card_owner', lazy='dynamic')

    @property
    def permissions(self):
        return Permissions.query.outerjoin(Elements).outerjoin(roles_elements).outerjoin(Roles).outerjoin(
            customer_role).outerjoin(
            Customers).filter(Customers.id.__eq__(self.id)).all()

    @property
    def elements(self):
        return Elements.query.outerjoin(roles_elements).outerjoin(Roles).outerjoin(customer_role).outerjoin(Customers). \
            filter(Customers.id == self.id).order_by(Elements.order).all()

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
        login_key = f"front::verification_code::{self.phone}"
        return True if redis_db.exists(login_key) and redis_db.get(login_key) == message else False

    def __repr__(self):
        return '<User %r>' % self.phone


class Users(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
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

    @property
    def permissions(self):
        return Permissions.query.outerjoin(Elements).outerjoin(roles_elements).outerjoin(Roles).outerjoin(
            user_role).outerjoin(
            Users).filter(Users.id.__eq__(self.id)).all()

    @property
    def elements(self):
        return Elements.query.outerjoin(roles_elements).outerjoin(Roles).outerjoin(user_role).outerjoin(Users). \
            filter(
            Users.id == self.id
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


class Brands(db.Model):
    __tablename__ = 'brands'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False, index=True)
    logo = db.Column(db.String(64), db.ForeignKey('img_url.id'))
    company_name = db.Column(db.String(100))
    company_address = db.Column(db.String(100))
    spu = db.relationship('SPU', backref='brand', lazy='dynamic')


class Classifies(db.Model):
    __tablename__ = 'classifies'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
    name = db.Column(db.String(50), nullable=False)
    spu = db.relationship('SPU', backref='classifies', lazy='dynamic')


class Standards(db.Model):
    __tablename__ = 'standards'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
    name = db.Column(db.String(50), nullable=False, unique=True, index=True)
    values = db.relationship('StandardValue', backref='standards', lazy='dynamic')


class StandardValue(db.Model):
    __tablename__ = 'standard_value'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
    standard_id = db.Column(db.String(64), db.ForeignKey('standards.id'))
    value = db.Column(db.String(50), nullable=False, unique=True, index=True)


class SPU(db.Model):
    __tablename__ = 'spu'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False, index=True)
    sub_name = db.Column(db.String(100))
    standards = db.relationship(
        'Standards',
        secondary=spu_standards,
        backref=db.backref(
            'spu'
        )
    )
    brand_id = db.Column(db.String(64), db.ForeignKey('brands.id'))
    classify_id = db.Column(db.String(64), db.ForeignKey('classifies.id'))
    sku = db.relationship('SKU', backref='the_spu', lazy='dynamic')


class ImgUrl(db.Model):
    __tablename__ = 'img_url'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
    path = db.Column(db.String(100), unique=True, nullable=False, index=True)
    attribute = db.Column(db.SmallInteger, default=1, index=True,
                          comment="1：轮播图  2：缩略图，用parent_id来关联对应的父级图  3：正文图片 4: banner图 5:logo")
    coupons = db.relationship('Coupons', backref="icon_url", lazy='dynamic')
    evaluates = db.relationship("Evaluates", backref="experience_url", lazy='dynamic')
    thumbnail_id = db.Column(db.String(64), db.ForeignKey('thumbnail_url.id'))
    brands = db.relationship('Brands', backref='logo_url', lazy='dynamic')
    customers = db.relationship('Customers', backref='photo_url', lazy='dynamic')


class ThumbnailUrl(db.Model):
    __tablename__ = 'thumbnail_url'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
    path = db.Column(db.String(100), unique=True, nullable=False, index=True)
    original_img = db.relationship('ImgUrl', backref='thumbnail_url', lazy='dynamic')


class PurchaseInfo(db.Model):
    __tablename__ = 'purchase_info'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
    sku_id = db.Column(db.String(64), db.ForeignKey('sku.id'))
    amount = db.Column(db.Integer)
    operator = db.Column(db.String(64))
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    status = db.Column(db.SmallInteger, default=1, comment="1 正常 0 作废")
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    memo = db.Column(db.String(200), comment="备忘，例如作废原因")


class SKU(db.Model):
    __tablename__ = 'sku'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False, index=True)
    price = db.Column(db.DECIMAL(7, 2), default=0.00)
    discount = db.Column(db.DECIMAL(3, 2), default=1.00)
    member_price = db.Column(db.DECIMAL(7, 2), default=0.00)
    score_types = db.Column(db.SmallInteger, default=0, comment='是否可用积分')
    contents = db.Column(db.Text(length=(2 ** 32) - 1))
    quantity = db.Column(db.Integer, default=0, index=True)
    spu_id = db.Column(db.String(64), db.ForeignKey('spu.id'))
    unit = db.Column(db.String(6), nullable=False)
    special = db.Column(db.SmallInteger, default=0, comment="0 非特价商品，1 特价商品， 2 赠品，不可单独销售")
    values = db.relationship(
        'StandardValue',
        secondary=sku_standardvalue,
        backref=db.backref('sku')
    )
    images = db.relationship(
        'ImgUrl',
        secondary=sku_img,
        backref=db.backref('img_sku')
    )
    status = db.Column(db.SmallInteger, default=0, comment="1 上架； 0 下架")
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    order = db.relationship(
        'ShopOrders',
        secondary=sku_shoporders,
        backref=db.backref('order_sku')
    )
    purchase_info = db.relationship('PurchaseInfo', backref='purchase_sku', lazy='dynamic')
    sku_layout = db.relationship('SKULayout', backref='layout_sku', lazy='dynamic')


class Coupons(db.Model):
    __tablename__ = 'coupons'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
    name = db.Column(db.String(64), nullable=False, comment="优惠券标题")
    icon = db.Column(db.String(64), db.ForeignKey('img_url.id'), comment="优惠券图标")
    used_in = db.Column(db.SmallInteger, nullable=False,
                        comment="可用于：10店铺优惠券 11新人店铺券  20商品优惠券  30类目优惠券  60平台优惠券 61新人平台券'")
    coupon_type = db.Column(db.SmallInteger, default=1, comment="1满减券 2叠加满减券 3无门槛券（需要限制大小）")
    with_special = db.Column(db.SmallInteger, default=2, comment="1可用于特价商品 2不能  默认不能(商品优惠卷除外)")
    with_sn = db.Column(db.String(64), comment='SPU或SKU ID')
    with_amount = db.Column(db.Integer, default=0, comment="满多少金额")
    used_amount = db.Column(db.Integer, comment="用券金额")
    quota = db.Column(db.Integer, default=1, comment='配额：发券数量')
    take_count = db.Column(db.Integer, default=0, comment='已领取的优惠券数量')
    used_count = db.Column(db.Integer, default=0, comment='已使用的优惠券数量')
    start_time = db.Column(db.DateTime, comment='发放开始时间')
    end_time = db.Column(db.DateTime, comment='发放结束时间')
    valid_type = db.Column(db.SmallInteger, default=2, comment='时效:1绝对时效（领取后XXX-XXX时间段有效）  2相对时效（领取后N天有效）')
    valid_days = db.Column(db.Integer, default=1, comment='自领取之日起有效天数')
    absolute_date = db.Column(db.DateTime, comment='当valid_type为1时，此项不能为空')
    status = db.Column(db.SmallInteger, comment='1生效 2失效 3已结束', default=1)
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    coupon_sent = db.relationship("CouponReady", backref='coupon_setting', lazy='dynamic')


class CouponReady(db.Model):
    __tablename__ = 'coupon_ready'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
    coupon_id = db.Column(db.String(64), db.ForeignKey('coupons.id'))
    status = db.Column(db.SmallInteger, default=1, comment="0: 作废，1：已领取未使用，2：已使用")
    take_at = db.Column(db.DateTime, default=datetime.datetime.now)
    use_at = db.Column(db.DateTime)
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    consumer = db.Column(db.String(64), db.ForeignKey('customers.id'))


class ShopOrders(db.Model):
    __tablename__ = 'shop_orders'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
    customer_id = db.Column(db.String(64), db.ForeignKey('customers.id'))
    trade_sn = db.Column(db.String(64), comment="微信支付的交易号")
    items_total_price = db.Column(db.DECIMAL(9, 2), default=0.00)
    score_used = db.Column(db.Integer, default=0, comment="使用的积分")
    is_pay = db.Column(db.SmallInteger, default=0, comment="默认0. 0：未支付， 1：完成支付， 2：支付失败")
    pay_time = db.Column(db.DateTime, comment="支付时间")
    is_ship = db.Column(db.SmallInteger, default=0, comment="0：未发货，1：已发货")
    ship_time = db.Column(db.DateTime, comment="发货时间")
    receive_time = db.Column(db.DateTime, comment="收货时间")
    is_receipt = db.Column(db.SmallInteger, default=0, comment="0：未发货 1：已发货未签收 2：已发货已签收")
    express_company = db.Column(db.String(50))
    express_number = db.Column(db.String(50))
    express_fee = db.Column(db.DECIMAL(7, 2), default=10.00)
    express_address = db.Column(db.String(64), db.ForeignKey('express_address.id'))
    status = db.Column(db.SmallInteger, default=1, comment="1：正常 2：禁用 0：订单取消")
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, onupdate=datetime.datetime.now)
    items_orders_id = db.relationship("ItemsOrders", backref='shop_orders', lazy='dynamic')
    message = db.Column(db.String(500), comment='用户留言')


class ItemsOrders(db.Model):
    __tablename__ = 'items_orders'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
    order_id = db.Column(db.String(64), db.ForeignKey('shop_orders.id'))
    item_id = db.Column(db.String(64), db.ForeignKey('sku.id'))
    item_quantity = db.Column(db.Integer, default=1)
    item_price = db.Column(db.DECIMAL(7, 2))
    activity_discount = db.Column(db.DECIMAL(3, 2), default=1.00)
    # 1：正常 2：禁用 0：取消
    status = db.Column(db.SmallInteger, default=1)
    create_at = db.Column(db.DateTime, default=datetime.datetime.now)
    update_at = db.Column(db.DateTime, default=datetime.datetime.now)
    rates = db.Column(db.String(64), db.ForeignKey('evaluates.id'))


class ExpressAddress(db.Model):
    __tablename__ = 'express_address'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
    sender = db.Column(db.String(64), db.ForeignKey('customers.id'))
    city_id = db.Column(db.Integer, db.ForeignKey('cities.id'))
    district = db.Column(db.Integer, db.ForeignKey('districts.id'))
    address1 = db.Column(db.String(100), nullable=False, comment="某某路xx号xx栋xx门牌号")
    address2 = db.Column(db.String(100))
    postcode = db.Column(db.String(10), comment="邮编")
    recipients = db.Column(db.String(50), nullable=False, comment="收件人")
    recipients_phone = db.Column(db.String(20), comment="收件人电话")
    status = db.Column(db.SmallInteger, default=1, comment="1：正常 0：删除")
    is_default = db.Column(db.Boolean, default=False)
    spu_order = db.relationship("ShopOrders", backref='express_to', lazy='dynamic')


class Evaluates(db.Model):
    __tablename__ = 'evaluates'
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
    express_rate = db.Column(db.SmallInteger, default=10, comment="物流评价0~10")
    item_rate = db.Column(db.SmallInteger, default=10, comment="商品评价0~10")
    content = db.Column(db.Text(length=(2 ** 32) - 1))
    used_pic = db.Column(db.String(64), db.ForeignKey('img_url.id'))
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
    id = db.Column(db.String(64), primary_key=True, default=str(uuid.uuid4()))
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
