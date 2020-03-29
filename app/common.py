from . import db, logger
from collections import defaultdict
from sqlalchemy.exc import SQLAlchemyError


def success_return(data="", message=""):
    return {"code": "success", "data": data, "message": message}


def false_return(data="", message=""):
    return {"code": "false", "data": data, "message": message}


def exp_return(data="", message=""):
    return {"code": "exp", "data": data, "message": message}


def session_commit():
    try:
        db.session.commit()
        return success_return(message="db commit success")
    except SQLAlchemyError as e:
        db.session.rollback()
        reason = str(e)
        logger.error(f"users::register::db_commit()::SQLAlchemyError --> {reason}")
        return false_return(message=reason)


def nesteddict():
    """
    构造一个嵌套的字典
    :return:
    """
    return defaultdict(nesteddict)



