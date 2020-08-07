"""empty message

Revision ID: 9b844ab9385c
Revises: c04bc30a7663
Create Date: 2020-04-12 15:40:40.994137

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9b844ab9385c'
down_revision = 'c04bc30a7663'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('coupon_ready', sa.Column('consumer', sa.String(length=64), nullable=True))
    op.create_foreign_key(None, 'coupon_ready', 'customers', ['consumer'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'coupon_ready', type_='foreignkey')
    op.drop_column('coupon_ready', 'consumer')
    # ### end Alembic commands ###
