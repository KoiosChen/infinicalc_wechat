from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from config import config
from flask_apscheduler import APScheduler
import logging
import redis
import queue
from flask_sqlalchemy import SQLAlchemy as SQLAlchemyBase
from sqlalchemy.pool import NullPool
from flask_restplus import Api
from fdfs_client.client import *
from qcloudsms_py import SmsSingleSender, SmsMultiSender
import threading
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix


class SQLAlchemy(SQLAlchemyBase):
    def apply_driver_hacks(self, app, info, options):
        super(SQLAlchemy, self).apply_driver_hacks(app, info, options)
        options['poolclass'] = NullPool
        options.pop('pool_size', None)


# 用于存放监控记录信息，例如UPS前序状态，需要配置持久化
redis_db = redis.Redis(host='localhost', port=6379, db=7, decode_responses=True)

db = SQLAlchemy()
scheduler = APScheduler()
default_api = Api(title='Infinicalc API', version='v0.1', prefix='/api', contact='chjz1226@gmail.com')

# 用于处理订单建议书的队列
work_q = queue.Queue(maxsize=100)

# 用于处理请求request的队列
request_q = queue.Queue(maxsize=1000)

logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %H:%M:%S')
logger = logging.getLogger()
hdlr = logging.FileHandler("run.log")
formatter = logging.Formatter(fmt='%(asctime)s - %(module)s-%(funcName)s - %(levelname)s - %(message)s',
                              datefmt='%m/%d/%Y %H:%M:%S')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.DEBUG)

tracker_path = get_tracker_conf('/etc/fdfs/client.conf')
fastdfs_client = Fdfs_client(tracker_path)
SECRET_KEY = '12kid9k29dj3nd8_2323'

# 短信应用 SDK AppID
appid = 1400348279  # SDK AppID 以1400开头
# 短信应用 SDK AppKey
appkey = "b31aa540ae287f0bc9cbca1667cf3865"
# 需要发送短信的手机号码
phone_numbers = ["13817730962", "15962968250‬"]
# 短信模板ID，需要在短信控制台中申请
template_id = 572001  # NOTE: 这里的模板 ID`7839`只是示例，真实的模板 ID 需要在短信控制台中申请
# 签名
sms_sign = "Infinicalc"

ssender = SmsSingleSender(appid, appkey)

coupon_lock = threading.Lock()
order_lock = threading.Lock()


def create_app(config_name):
    app = Flask(__name__)
    # CORS(app)
    app.config.from_object(config[config_name])
    app.wsgi_app = ProxyFix(app.wsgi_app)
    config[config_name].init_app(app)
    db.app = app
    db.init_app(app)
    default_api.init_app(app)
    db.create_scoped_session()
    scheduler.init_app(app)
    scheduler.start()

    @default_api.errorhandler(Exception)
    def generic_exception_handler(e: Exception):
        logger.error(">>>>>" + str(e))
        return {'message': f'Internal Server Error {e}'}, 500

    @app.errorhandler(Exception)
    def app_generic_exception_handler(e: Exception):
        logger.error(">>>>>" + str(e))
        return {'message': f'Internal Server Error {e}'}, 500


    @app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Origin', '*')
        if request.method == 'OPTIONS':
            response.headers['Access-Control-Allow-Methods'] = 'DELETE, GET, POST, PUT'
            headers = request.headers.get('Access-Control-Request-Headers')
            if headers:
                response.headers['Access-Control-Allow-Headers'] = headers
        return response

    from .users import users as users_blueprint
    app.register_blueprint(users_blueprint)

    from .roles import roles as roles_blueprint
    app.register_blueprint(roles_blueprint)

    from .mall import mall as mall_blueprint
    app.register_blueprint(mall_blueprint)

    from .elements import elements as elements_blueprint
    app.register_blueprint(elements_blueprint)

    from .img_urls import img_urls as img_urls_blueprint
    app.register_blueprint(img_urls_blueprint)

    from .layout import layout as layout_blueprint
    app.register_blueprint(layout_blueprint)

    from .sms import sms as sms_blueprint
    app.register_blueprint(sms_blueprint)

    from .customers import customers as customers_blueprint
    app.register_blueprint(customers_blueprint)

    from .promotion_groups import promotion_groups as promotion_groups_blueprint
    app.register_blueprint(promotion_groups_blueprint)

    from .promotions import promotions as promotions_blueprint
    app.register_blueprint(promotions_blueprint)

    from .shopping_cart import shopping_cart as shopping_cart_blueprint
    app.register_blueprint(shopping_cart_blueprint)

    return app
