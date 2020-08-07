"""empty message

Revision ID: 6e9f71cf0ab2
Revises: f4969ecad31b
Create Date: 2020-07-15 20:49:17.590165

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '6e9f71cf0ab2'
down_revision = 'f4969ecad31b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('obj_storage_ibfk_1', 'obj_storage', type_='foreignkey')
    op.drop_column('obj_storage', 'thumbnail_id')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('obj_storage', sa.Column('thumbnail_id', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=True))
    op.create_foreign_key('obj_storage_ibfk_1', 'obj_storage', 'thumbnail_url', ['thumbnail_id'], ['id'])
    # ### end Alembic commands ###
