import requests


class WxLogin(object):
    def __init__(self, jscode):
        __app_id = "wxbd90eb9673088c7b"
        __app_secret = "3aa0c3296b1ee4ef09bf9f3c0a43b7ff"
        __url = "https://api.weixin.qq.com/sns/jscode2session"
        __params = {"appid": __app_id, "secret": __app_secret, "js_code": jscode,
                    "grant_type": "authorization_code"}
        r = requests.get(__url, params=__params)
        self.response = r.json()

    def get_openid(self):
        return self.response.get('openid')

    def get_session_key(self):
        return self.response.get('session_key')
