"""empty message

Revision ID: 6066c90c1f96
Revises: 6e9f71cf0ab2
Create Date: 2020-07-15 20:49:46.019318

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '6066c90c1f96'
down_revision = '6e9f71cf0ab2'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_thumbnail_url_path', table_name='thumbnail_url')
    op.drop_table('thumbnail_url')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('thumbnail_url',
    sa.Column('id', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('path', mysql.VARCHAR(collation='utf8_bin', length=100), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8_bin',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_index('ix_thumbnail_url_path', 'thumbnail_url', ['path'], unique=True)
    # ### end Alembic commands ###
