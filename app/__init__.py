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
import multiprocessing
from fdfs_client.client import *


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

tracker_path = get_tracker_conf('/Users/Peter/fastdfs/client.conf')
fastdfs_client = Fdfs_client(tracker_path)
SECRET_KEY = '12kid9k29dj3nd8_2323'


def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    db.app = app
    db.init_app(app)
    default_api.init_app(app)
    db.create_scoped_session()
    scheduler.init_app(app)
    scheduler.start()

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

    from .menus import menus as menus_blueprint
    app.register_blueprint(menus_blueprint)

    from .permissions import permissions as permissions_blueprint
    app.register_blueprint(permissions_blueprint)

    from .img_urls import img_urls as img_urls_blueprint
    app.register_blueprint(img_urls_blueprint)

    return app
