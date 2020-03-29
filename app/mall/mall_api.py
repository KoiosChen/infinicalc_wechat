from .. import default_api
from ..swagger import return_dict

mall_ns = default_api.namespace('mall', path='/mall',
                                description='Items list that recommended, all items list'
                                            'Product add, product delete, product setting, '
                                            'Add discount coupon, delete discount coupon, '
                                            'Check the coupon, consume the coupon'
                                            'Add item to shopping cart, delete item from shopping cart,'
                                            'Change the number of product in the order,getting user\'s role')

return_json = mall_ns.model('ReturnRegister', return_dict)
