"""empty message

Revision ID: 7d97ba118a7e
Revises: 3f928c3a02d5
Create Date: 2020-07-27 14:50:13.498011

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '7d97ba118a7e'
down_revision = '3f928c3a02d5'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('rebates',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('member_type', sa.SmallInteger(), nullable=True, comment='0: 直客，1: 代理'),
    sa.Column('member_grade', sa.SmallInteger(), nullable=True, comment='1: 一级代理， 2： 二级代理；直客忽略此字段'),
    sa.Column('invitor_grade', sa.SmallInteger(), nullable=True, comment='1 表示上级发展来下的下级，0，表示平级或者下级发展来的代理'),
    sa.Column('self_rebate', sa.DECIMAL(precision=5, scale=2), nullable=True, comment='填写百分比，譬如30.00, 表示返佣30%'),
    sa.Column('parent_rebate', sa.DECIMAL(precision=5, scale=2), nullable=True, comment='父级返佣比例'),
    sa.Column('grandparent_rebate', sa.DECIMAL(precision=5, scale=2), nullable=True, comment='祖父级返佣比例'),
    sa.Column('invitor_second_level_rebate', sa.DECIMAL(precision=5, scale=2), nullable=True, comment='邀请者返佣比例，目前指邀请成功的二级 5%'),
    sa.Column('invite_first_level_bonus', sa.DECIMAL(precision=7, scale=2), nullable=True, comment='成功邀请一个一级的奖金'),
    sa.Column('c_to_c_bonus_score', sa.DECIMAL(precision=5, scale=2), nullable=True, comment='c to c 可获取的奖励积分, 这里的百分比是消费额的百分比作为积分'),
    sa.Column('create_at', sa.DateTime(), nullable=True),
    sa.Column('update_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('shop_order_status',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('shop_order_id', sa.String(length=64), nullable=True),
    sa.Column('customer_id', sa.String(length=64), nullable=True),
    sa.Column('character', sa.SmallInteger(), nullable=True, comment='0: 购买者； 1: 代理关系上级 2: '),
    sa.Column('member_type', sa.SmallInteger(), nullable=True, comment='付款是用户的类型'),
    sa.Column('member_level', sa.SmallInteger(), nullable=True, comment='付款时用户的级别'),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    sa.ForeignKeyConstraint(['shop_order_id'], ['shop_orders.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.alter_column('customers', 'invitor_id',
               existing_type=mysql.VARCHAR(collation='utf8_bin', length=64),
               comment='代理商邀请',
               existing_nullable=True)
    op.alter_column('customers', 'parent_id',
               existing_type=mysql.VARCHAR(collation='utf8_bin', length=64),
               comment='邀请者，分享小程序入口之后的级联关系写在invitor中',
               existing_nullable=True)
    op.add_column('invitation_code', sa.Column('validity_at', sa.DateTime(), nullable=True))
    op.add_column('items_orders', sa.Column('delete_at', sa.DateTime(), nullable=True))
    op.add_column('member_cards', sa.Column('invitor_grade', sa.SmallInteger(), nullable=True, comment='1,上级发展下级；0 下级或者评价发展成为的代理'))
    op.add_column('shop_orders', sa.Column('delete_at', sa.DateTime(), nullable=True))
    op.alter_column('sku', 'could_get_coupon_id',
               existing_type=mysql.VARCHAR(collation='utf8_bin', length=64),
               comment='如果是直客，那么可以设置获取优惠券',
               existing_nullable=True)
    op.drop_column('sku', 'agent_second_rebate')
    op.drop_column('sku', 'agent_first_rebate')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('sku', sa.Column('agent_first_rebate', mysql.DECIMAL(precision=7, scale=2), nullable=True, comment='一级代理商返佣'))
    op.add_column('sku', sa.Column('agent_second_rebate', mysql.DECIMAL(precision=7, scale=2), nullable=True, comment='二级代理商返佣'))
    op.alter_column('sku', 'could_get_coupon_id',
               existing_type=mysql.VARCHAR(collation='utf8_bin', length=64),
               comment=None,
               existing_comment='如果是直客，那么可以设置获取优惠券',
               existing_nullable=True)
    op.drop_column('shop_orders', 'delete_at')
    op.drop_column('member_cards', 'invitor_grade')
    op.drop_column('items_orders', 'delete_at')
    op.drop_column('invitation_code', 'validity_at')
    op.alter_column('customers', 'parent_id',
               existing_type=mysql.VARCHAR(collation='utf8_bin', length=64),
               comment=None,
               existing_comment='邀请者，分享小程序入口之后的级联关系写在invitor中',
               existing_nullable=True)
    op.alter_column('customers', 'invitor_id',
               existing_type=mysql.VARCHAR(collation='utf8_bin', length=64),
               comment=None,
               existing_comment='代理商邀请',
               existing_nullable=True)
    op.drop_table('shop_order_status')
    op.drop_table('rebates')
    # ### end Alembic commands ###
