"""empty message

Revision ID: 3ca42c78e9af
Revises: 23405ea82fc4
Create Date: 2020-04-25 21:00:11.574991

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '3ca42c78e9af'
down_revision = '23405ea82fc4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('benefits', sa.Column('pay_more', sa.DECIMAL(precision=7, scale=2), nullable=True, comment='加价购，可选范围在gifts中，由pay_more_quantity来控制加价购可选商品数量'))
    op.add_column('benefits', sa.Column('pay_more_quantity', sa.SmallInteger(), nullable=True, comment='控制加价购数量'))
    op.add_column('promotions', sa.Column('combo_price', sa.DECIMAL(precision=7, scale=2), nullable=True, comment='仅当活动类型是4时生效, 只允许添加sku'))
    op.add_column('promotions', sa.Column('presell_multiple', sa.DECIMAL(precision=3, scale=2), nullable=True, comment='预售定金倍数，例如定金是10元，倍数是1.5，那么抵扣商品15元'))
    op.add_column('promotions', sa.Column('presell_price', sa.DECIMAL(precision=7, scale=2), nullable=True, comment='当类型是5时， 设置预售定金'))
    op.alter_column('promotions', 'promotion_type',
               existing_type=mysql.SMALLINT(display_width=6),
               comment='0: 满减，1：满赠，2：满折，3：加价购，4：套餐，5：预售, 6：秒杀',
               existing_comment='促销类型',
               existing_nullable=True)
    op.add_column('sku', sa.Column('seckill_price', sa.DECIMAL(precision=7, scale=2), nullable=True, comment='当SKU参加秒杀活动时，设置秒杀价格写在这个字段，如果不为0， 则表示参加秒杀，查找秒杀活动'))
    op.add_column('sku', sa.Column('show_price', sa.String(length=9), nullable=True, comment='显示价格， 当special不为0时，显示此价格，并且用删除线'))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('sku', 'show_price')
    op.drop_column('sku', 'seckill_price')
    op.alter_column('promotions', 'promotion_type',
               existing_type=mysql.SMALLINT(display_width=6),
               comment='促销类型',
               existing_comment='0: 满减，1：满赠，2：满折，3：加价购，4：套餐，5：预售, 6：秒杀',
               existing_nullable=True)
    op.drop_column('promotions', 'presell_price')
    op.drop_column('promotions', 'presell_multiple')
    op.drop_column('promotions', 'combo_price')
    op.drop_column('benefits', 'pay_more_quantity')
    op.drop_column('benefits', 'pay_more')
    # ### end Alembic commands ###
