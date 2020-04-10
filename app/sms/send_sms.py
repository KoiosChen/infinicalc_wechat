import random
from .. import ssender, redis_db
from qcloudsms_py.httpclient import HTTPError
from ..common import success_return, false_return


def general_verification_code(code_len=6):
    code = ""
    for _ in range(code_len):
        code += str(random.randint(1, 9))
    return code


def send_verification_code(phone, template_id, sms_sign):
    code = general_verification_code()
    params = [code]
    try:
        result = ssender.send_with_param(86, phone, template_id, params, sign=sms_sign, extend="", ext="")
        redis_db.set(f"verification_code::{phone}", code)
        redis_db.expire(f"verification_code::{phone}", 125)
    except HTTPError as e:
        return false_return(message=f"短信发送失败，HTTPError: {e}")
    except Exception as e:
        return false_return(message=f"短信发送失败，{e}")
    return success_return(data=result, message="短信已发送")
