"""empty message

Revision ID: 52fa38561abf
Revises: 5dfe96bcfc4b
Create Date: 2020-04-03 13:59:38.432618

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '52fa38561abf'
down_revision = '5dfe96bcfc4b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('purchase_info',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('sku_id', sa.String(length=64), nullable=True),
    sa.Column('unit', sa.String(length=6), nullable=False),
    sa.Column('amount', sa.Integer(), nullable=True),
    sa.Column('operator', sa.String(length=18), nullable=True),
    sa.Column('create_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['sku_id'], ['sku.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('purchase_info')
    # ### end Alembic commands ###
