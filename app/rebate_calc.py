from app.models import ItemsOrders, ShopOrders, Customers, BusinessUnits, BusinessUnitEmployees, CustomerRoles, \
    CloudWineRebates
from decimal import Decimal


def get_rebate(role_name, sku_id, level, scene):
    role_id = CustomerRoles.query.filter_by(name=role_name).first().id
    return CloudWineRebates.query.filter(CloudWineRebates.role_id.__eq__(role_id),
                                         CloudWineRebates.sku_id.__eq__(sku_id),
                                         CloudWineRebates.consumer_level.__eq__(level),
                                         CloudWineRebates.scene.__eq__(scene),
                                         CloudWineRebates.status.__eq__(1),
                                         CloudWineRebates.delete_at.__eq__(None)).first()


def bu_rebate(employee, waiter_rebate, operator_rebate, manager_rebate):
    pk_rebate = Decimal("0.00")
    if employee.job_desc == "BU_WAITER":
        pk_rebate = waiter_rebate.rebate
    elif employee.job_desc == "BU_OPERATOR":
        pk_rebate = waiter_rebate.rebate + operator_rebate.rebate
    elif employee.job_desc == "BU_MANAGER":
        pk_rebate = waiter_rebate.rebate + operator_rebate.rebate + manager_rebate.rebate

    return pk_rebate


def purchase_rebate(consumer_id, item_order_id):
    """
    购买场景的返佣
    :param consumer_id:
    :param item_order_id:
    :return:
    """
    consumer_obj = Customers.query.get(consumer_id)
    bu_obj = consumer_obj.business_unit_employee.business_unit
    franchisee_obj = bu_obj.franchisee
    franchisee_operators = franchisee_obj.operators
    sku_id = ItemsOrders.query.get(item_order_id).item_id

    kwargs = {"sku_id": sku_id, "level": consumer_obj.level, "scene": "PURCHASE"}
    f_manager_rebate = get_rebate("FRANCHISEE_MANAGER", **kwargs)
    bu_manager_rebate = get_rebate("BU_MANAGER", **kwargs)
    bu_operator_rebate = get_rebate("BU_OPERATOR", **kwargs)
    bu_waiter_rebate = get_rebate("BU_WAITER", **kwargs)

    for fo in franchisee_operators:
        if fo.job_desc == CustomerRoles.query.filter_by(name='FRANCHISEE_MANAGER'):
            the_purchase_rebate = f_manager_rebate.rebate
            fo.operator_wechat.purse += the_purchase_rebate
            break

    the_purchase_rebate = bu_rebate(consumer_obj.business_unit_employee, waiter_rebate=bu_waiter_rebate,
                                    operator_rebate=bu_operator_rebate, manager_rebate=bu_manager_rebate)

    consumer_obj.business_unit_employee.employee_wechat.purse += the_purchase_rebate

    return True


def pickup_rebate(item_order_id, pickup_employee_id, consumer_id):
    """
    取酒场景触发的返佣。取酒场景，先判断订单是否为快递订单，如果是，则不能产生取酒返佣，且不能取酒。
    :param item_order_id:
    :param pickup_employee_id:
    :param consumer_id:
    :return:
    """
    # first order rebate
    item_obj = ItemsOrders.query.get(item_order_id)
    shop_order_obj = item_obj.shop_orders
    consumer_obj = Customers.query.get(consumer_id)
    if consumer_obj.first_order_table == shop_order_obj.__class__.__name__ and consumer_obj.first_order_id == shop_order_obj.id:
        # 表明当前item order 属于首单，调用 purchase_rebate来计算购买返佣
        purchase_rebate(consumer_id, item_order_id)

    pickup_employee = BusinessUnitEmployees.query.get(pickup_employee_id)
    kwargs = {"sku_id": item_obj.item_id, "level": consumer_obj.level, "scene": "PICKUP"}
    waiter_rebate = get_rebate("BU_MANAGER", **kwargs)
    operator_rebate = get_rebate("BU_OPERATOR", **kwargs)
    manager_rebate = get_rebate("BU_MANAGER", **kwargs)

    pk_rebate = bu_rebate(pickup_employee, waiter_rebate, operator_rebate, manager_rebate)

    # 店铺取酒返佣
    pickup_employee.employee_wechat.purse += pk_rebate
