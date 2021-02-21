from app import redis_db
import json
import datetime
import requests
from app.wechat.wechat_config import LBS_KEY, LBS_COORDINATE_URL
from app.public_method import success_return, false_return


def lbs_get_by_coordinate(lat, lng):
    try:
        if redis_db.exists('access_token'):
            token = json.loads(redis_db.get('access_token'))
            if datetime.datetime.now().timestamp() <= token['now_time'] + token['expires_in']:
                return token['access_token']

        params = {"location": f"{lat},{lng}", "key": LBS_KEY}
        req = requests.get(LBS_COORDINATE_URL, params=params)
        if req.status_code != 200:
            raise Exception("请求接口失败, request返回值非200")
        content = req.json()
        if content['status'] != 0:
            raise Exception(content['message'])
        address = content['result']['address_component']
        if address['province'] != address['city']:
            # addr_join = address['nation'] + address['province'] + address['city'] + address['district']
            addr = [address['nation'], address['province'], address['city'], address['district']]
        else:
            addr = [address['nation'], address['province'], address['district']]
        return success_return(data=addr)
    except Exception as e:
        return false_return(message=str(e))


if __name__ == "__main__":
    print(lbs_get_by_coordinate("39.984154", "116.307490"))
    a = {'status': 0, 'message': 'query ok', 'request_id': '7c30bd08-0708-11eb-b229-5254007f724b',
         'result': {'location': {'lat': 39.984154, 'lng': 116.30749}, 'address': '北京市海淀区北四环西路66号',
                    'formatted_addresses': {'recommend': '海淀区中关村中国技术交易大厦(彩和坊路)', 'rough': '海淀区中关村中国技术交易大厦(彩和坊路)'},
                    'address_component': {'nation': '中国', 'province': '北京市', 'city': '北京市', 'district': '海淀区',
                                          'street': '北四环西路', 'street_number': '北四环西路66号'},
                    'ad_info': {'nation_code': '156', 'adcode': '110108', 'city_code': '156110000',
                                'name': '中国,北京市,北京市,海淀区', 'location': {'lat': 40.045132, 'lng': 116.375},
                                'nation': '中国', 'province': '北京市', 'city': '北京市', 'district': '海淀区'},
                    'address_reference': {'business_area': {'id': '14178584199053362783', 'title': '中关村',
                                                            'location': {'lat': 39.980598, 'lng': 116.310997},
                                                            '_distance': 0, '_dir_desc': '内'},
                                          'famous_area': {'id': '14178584199053362783', 'title': '中关村',
                                                          'location': {'lat': 39.980598, 'lng': 116.310997},
                                                          '_distance': 0, '_dir_desc': '内'},
                                          'crossroad': {'id': '529979', 'title': '海淀大街/彩和坊路(路口)',
                                                        'location': {'lat': 39.982498, 'lng': 116.30809},
                                                        '_distance': 185.8, '_dir_desc': '北'},
                                          'town': {'id': '110108012', 'title': '海淀街道',
                                                   'location': {'lat': 39.974819, 'lng': 116.284409}, '_distance': 0,
                                                   '_dir_desc': '内'},
                                          'street_number': {'id': '595672509379194165901290', 'title': '北四环西路66号',
                                                            'location': {'lat': 39.984089, 'lng': 116.308037},
                                                            '_distance': 45.8, '_dir_desc': ''},
                                          'street': {'id': '9217092216709107946', 'title': '彩和坊路',
                                                     'location': {'lat': 39.97921, 'lng': 116.308411},
                                                     '_distance': 46.6, '_dir_desc': '西'},
                                          'landmark_l2': {'id': '3629720141162880123', 'title': '中国技术交易大厦',
                                                          'location': {'lat': 39.984253, 'lng': 116.307472},
                                                          '_distance': 0, '_dir_desc': '内'}}},
         'now_time': 1601901858.998812}
