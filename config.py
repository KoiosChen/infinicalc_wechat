import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard to guess string'
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    SQLALCHEMY_TRACK_MODIFICATIONS = True
    SESSION_TYPE = 'redis'
    SESSION_KEY_PREFIX = 'flask_session:'
    SESSION_PERMANENT = True
    SESSION_USE_SIGNER = True

    SQLALCHEMY_POOL_RECYCLE = 1800
    FLASKY_ADMIN = 'peter.chen@mbqianbao.com'

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    DB_USERNAME = os.environ.get('DEV_DATABASE_USERNAME') or 'peter'
    DB_PASSWORD = os.environ.get('DEV_DATABASE_PASSWORD') or '123123'
    DB_HOST = os.environ.get('DEV_DATABASE_HOST') or '127.0.0.1'
    DB_DATABASE = os.environ.get('DEV_DATABASE_DATABASE') or 'infinicalc'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://' + DB_USERNAME + ':' + DB_PASSWORD + '@' + DB_HOST + '/' + DB_DATABASE


class TestingConfig(Config):
    DEBUG = False
    DB_USERNAME = os.environ.get('TEST_DATABASE_USERNAME') or 'peter'
    DB_PASSWORD = os.environ.get('TEST_DATABASE_PASSWORD') or 'Ftp123buzhidao_'
    DB_HOST = os.environ.get('TEST_DATABASE_HOST') or '127.0.0.1'
    DB_DATABASE = os.environ.get('TEST_DATABASE_DATABASE') or 'infinicalc'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://' + DB_USERNAME + ':' + DB_PASSWORD + '@' + DB_HOST + '/' + DB_DATABASE


class ProductionConfig(Config):
    DB_USERNAME = os.environ.get('DATABASE_USERNAME') or 'peter'
    DB_PASSWORD = os.environ.get('DATABASE_PASSWORD') or 'Gamefast_1324'
    DB_HOST = os.environ.get('DATABASE_HOST') or '127.0.0.1'
    DB_DATABASE = os.environ.get('DATABASE_DATABASE') or 'gamefast'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://' + DB_USERNAME + ':' + DB_PASSWORD + '@' + DB_HOST + '/' + DB_DATABASE


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}