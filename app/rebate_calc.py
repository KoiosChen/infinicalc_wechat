from app.models import ItemsOrders, ShopOrders, Customers, BusinessUnits, BusinessUnitEmployees, CustomerRoles, \
    CloudWineRebates


def purchase_rebate(*args, **kwargs):
    """
    购买场景的返佣
    :param args:
    :param kwargs:
    :return:
    """
    pass


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
    shop_order_obj = item_obj.shop_orders.first()
    consumer_obj = Customers.query.get(consumer_id)
    bu_obj = BusinessUnitEmployees.query.get(pickup_employee_id).business_unit
    if consumer_obj.first_order_table == shop_order_obj.__class__.__name__ and consumer_obj.first_order_id == shop_order_obj.id:
        # 表明当前item order 属于首单，调用 purchase_rebate来计算购买返佣
        pass

    bu_employees = bu_obj.employees
    manager_role = CustomerRoles.query.filter_by(name='BU_MANAGER')
    operator_role = CustomerRoles.query.filter_by(name='BU_OPERATOR')
    waiter_role = CustomerRoles.query.filter_by(name='BU_WAITER')
    bu_manager = bu_employees.filter_by(job_desc=manager_role.id).all()
    bu_operator = bu_employees.filter_by(job_desc=operator_role.id).all()
    waiter_rebate = CloudWineRebates.query.filter(CloudWineRebates.role_id.__eq__(waiter_role.id),
                                                  CloudWineRebates.sku_id.__eq__(item_obj.item_id),
                                                  CloudWineRebates.consumer_level.__eq__(consumer_obj.level),
                                                  CloudWineRebates.scene.__eq__('PICKUP'),
                                                  CloudWineRebates.status.__eq__(1),
                                                  CloudWineRebates.delete_at.__eq__(None)).first()
    operator_rebate = CloudWineRebates.query.filter(CloudWineRebates.role_id.__eq__(operator_role.id),
                                                    CloudWineRebates.sku_id.__eq__(item_obj.item_id),
                                                    CloudWineRebates.consumer_level.__eq__(consumer_obj.level),
                                                    CloudWineRebates.scene.__eq__('PICKUP'),
                                                    CloudWineRebates.status.__eq__(1),
                                                    CloudWineRebates.delete_at.__eq__(None)).first()
    manager_rebate = CloudWineRebates.query.filter(CloudWineRebates.role_id.__eq__(manager_role.id),
                                                   CloudWineRebates.sku_id.__eq__(item_obj.item_id),
                                                   CloudWineRebates.consumer_level.__eq__(consumer_obj.level),
                                                   CloudWineRebates.scene.__eq__('PICKUP'),
                                                   CloudWineRebates.status.__eq__(1),
                                                   CloudWineRebates.delete_at.__eq__(None)).first()
