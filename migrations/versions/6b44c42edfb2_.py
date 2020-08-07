"""empty message

Revision ID: 6b44c42edfb2
Revises: 7d97ba118a7e
Create Date: 2020-07-31 09:25:10.807334

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6b44c42edfb2'
down_revision = '7d97ba118a7e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('member_cards', sa.Column('invitor_id', sa.String(length=64), nullable=True))
    op.create_foreign_key(None, 'member_cards', 'customers', ['invitor_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'member_cards', type_='foreignkey')
    op.drop_column('member_cards', 'invitor_id')
    # ### end Alembic commands ###
