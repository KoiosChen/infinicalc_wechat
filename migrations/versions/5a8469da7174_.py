"""empty message

Revision ID: 5a8469da7174
Revises: c8b28ba8b8ea
Create Date: 2020-08-11 22:29:40.029238

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '5a8469da7174'
down_revision = 'c8b28ba8b8ea'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('express_address', sa.Column('recipient', sa.String(length=50), nullable=True, comment='收件人'))
    op.add_column('express_address', sa.Column('recipient_phone', sa.String(length=20), nullable=True, comment='收件人电话'))
    op.drop_column('express_address', 'recipients')
    op.drop_column('express_address', 'recipients_phone')
    op.add_column('shop_orders', sa.Column('express_address', sa.String(length=200), nullable=True, comment='记录下单时发货地址，防止地址记录修改。 原express_address表中address1+address2'))
    op.add_column('shop_orders', sa.Column('express_postcode', sa.String(length=7), nullable=True, comment='邮编'))
    op.add_column('shop_orders', sa.Column('express_recipient', sa.String(length=20), nullable=True, comment='收件人'))
    op.add_column('shop_orders', sa.Column('express_recipient_phone', sa.String(length=13), nullable=True, comment='收件人手机号'))
    op.alter_column('shop_orders', 'items_total_price',
               existing_type=mysql.DECIMAL(precision=9, scale=2),
               comment='未使用积分的总价',
               existing_nullable=True)
    op.drop_column('shop_orders', 'express_address_record')
    op.add_column('sku', sa.Column('get_score', sa.Integer(), nullable=True, comment='可以获得的积分'))
    op.add_column('sku', sa.Column('max_score', sa.Integer(), nullable=True, comment='最多可用积分'))
    op.drop_column('sku', 'score')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('sku', sa.Column('score', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True, comment='积分'))
    op.drop_column('sku', 'max_score')
    op.drop_column('sku', 'get_score')
    op.add_column('shop_orders', sa.Column('express_address_record', mysql.VARCHAR(collation='utf8_bin', length=200), nullable=True, comment='记录下单时发货地址，防止地址记录修改'))
    op.alter_column('shop_orders', 'items_total_price',
               existing_type=mysql.DECIMAL(precision=9, scale=2),
               comment=None,
               existing_comment='未使用积分的总价',
               existing_nullable=True)
    op.drop_column('shop_orders', 'express_recipient_phone')
    op.drop_column('shop_orders', 'express_recipient')
    op.drop_column('shop_orders', 'express_postcode')
    op.drop_column('shop_orders', 'express_address')
    op.add_column('express_address', sa.Column('recipients_phone', mysql.VARCHAR(collation='utf8_bin', length=20), nullable=True, comment='收件人电话'))
    op.add_column('express_address', sa.Column('recipients', mysql.VARCHAR(collation='utf8_bin', length=50), nullable=True, comment='收件人'))
    op.drop_column('express_address', 'recipient_phone')
    op.drop_column('express_address', 'recipient')
    # ### end Alembic commands ###
