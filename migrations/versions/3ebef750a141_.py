"""empty message

Revision ID: 3ebef750a141
Revises: 839bcd66453c
Create Date: 2020-04-05 00:48:39.251522

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3ebef750a141'
down_revision = '839bcd66453c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('purchase_info', sa.Column('status', sa.SmallInteger(), nullable=True, comment='1 正常 0 作废'))
    op.add_column('purchase_info', sa.Column('update_at', sa.DateTime(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('purchase_info', 'update_at')
    op.drop_column('purchase_info', 'status')
    # ### end Alembic commands ###
