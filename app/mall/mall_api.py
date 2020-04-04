from .. import default_api
from ..swagger import return_dict

mall_ns = default_api.namespace('mall', path='/mall',
                                description='商城相关接口')

return_json = mall_ns.model('ReturnRegister', return_dict)
