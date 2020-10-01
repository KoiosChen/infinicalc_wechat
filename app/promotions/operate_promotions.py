from ..models import SKU, SPU, Classifies, Brands, Gifts, Benefits, Promotions
from .. import db
from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import new_data_obj


class AddPromotions:
    """新增活动"""

    def __init__(self, args):
        self.args = args
        self.promotion_type = args.pop('promotion_type')
        self.promotion_name = args.pop('name')
        self.promotion_group = args.pop('group')
        self.promotion_scope_dict = {'brands': Brands, 'classifies': Classifies, 'spu': SPU, 'sku': SKU}
        self.new_promotion = None

    def new_base_promotion(self):
        self.new_promotion = new_data_obj('Promotions',
                                          **{"name": self.promotion_name,
                                             "promotion_type": self.promotion_type,
                                             "group": self.promotion_group})
        if self.new_promotion.get('status'):
            obj = self.new_promotion['obj']
            for k, v in self.args.items():
                if k not in self.promotion_scope_dict.keys() and k != 'benefits':
                    setattr(obj, k, v)
            db.session.add(obj)
            db.session.flush()
            return success_return(data={'id': obj.id}, message='活动规则添加成功')
        else:
            return false_return(message='活动已存在')

    def new_scopes(self):
        """促销活动范围"""
        obj = self.new_promotion.get('obj')
        for k, v in self.promotion_scope_dict.items():
            if k in self.args.keys():
                for s in self.args.get(k):
                    if s:
                        scope_obj = v.query.get(s['id'])
                        if 'seckill_price' in s.keys():
                            setattr(scope_obj, 'seckill_price', s['seckill_price'])
                        if 'per_user' in s.keys():
                            setattr(scope_obj, 'per_user', s['per_user'])
                        getattr(getattr(obj, k), 'append')(scope_obj)

    def new_benefits(self):
        obj = self.new_promotion.get('obj')
        if self.args.get('benefits'):
            if self.args.get('accumulation') == 1:
                benefit_list = self.args['benefits']
            else:
                benefit_list = self.args['benefits'][0:1]
            for benefit in benefit_list:
                benefit['name'] = self.promotion_name
                if 'gifts' in benefit.keys():
                    gifts = benefit.pop('gifts')
                else:
                    gifts = []
                new_benefit = new_data_obj('Benefits', **benefit)
                if new_benefit.get('status'):
                    for gift in gifts:
                        # {'sku': sku.id, 'discount': float, 'benefit': benefits.id}
                        tmp_gift = dict()
                        tmp_gift['sku'] = gift
                        tmp_gift['benefit'] = new_benefit.get('obj').id
                        new_data_obj('Gifts', **tmp_gift)
                    obj.benefits.append(new_benefit['obj'])
                else:
                    return false_return(message=f"活动利益表添加失败，{benefit}已存在")
            return success_return(message='添加活动利益表成功')
        else:
            return false_return(message='无benefit数据')

    def new_coupons(self):
        obj = self.new_promotion.get('obj')
        new_coupon = new_data_obj('Coupons', **{'name': self.promotion_name,
                                                'icon': self.args.get('icon'),
                                                'quota': self.args.get('quota'),
                                                'per_user': self.args.get('per_user'),
                                                'valid_type': self.args.get('valid_type')})

        if new_coupon.get('status'):
            if self.args.get('valid_type') == 1:
                if not self.args.get('absolute_date'):
                    return false_return(message=f'valid_type 为1时， absolute_date不能为空')
                setattr(new_coupon['obj'], 'absolute_date', self.args.get('absolute_date'))
            elif self.args.get('valid_type') == 2:
                if not self.args.get('valid_days'):
                    return false_return(message=f'valid_type 为2时， valid_days不能为空')
                setattr(new_coupon['obj'], 'valid_days', self.args.get('valid_days'))
            elif self.args.get('valid_type') not in (1, 2):
                return false_return(message=f"valid_type 错误")
            obj.coupon = new_coupon['obj']
            return submit_return('create coupon setting success', "create coupon fail")
        else:
            return false_return(message=f"coupon already exist"), 400


class UpdatePromotions:
    def __init__(self, promotion_id):
        self.promotion = Promotions.query.get(promotion_id)

    def update_scope(self):
        pass

    def update_benefit(self):
        pass

    def update_coupon(self):
        pass
