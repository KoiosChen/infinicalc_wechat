"""empty message

Revision ID: d391b59b6506
Revises: 64dfd4e3a9fc
Create Date: 2020-07-16 07:43:10.875240

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'd391b59b6506'
down_revision = '64dfd4e3a9fc'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('spu_obj',
    sa.Column('spu_id', sa.String(length=64), nullable=False),
    sa.Column('obj_id', sa.String(length=64), nullable=False),
    sa.Column('create_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['obj_id'], ['obj_storage.id'], ),
    sa.ForeignKeyConstraint(['spu_id'], ['spu.id'], ),
    sa.PrimaryKeyConstraint('spu_id', 'obj_id')
    )
    op.drop_table('spu_img')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('spu_img',
    sa.Column('spu_id', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('img_id', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False),
    sa.Column('create_at', mysql.DATETIME(), nullable=True),
    sa.ForeignKeyConstraint(['img_id'], ['img_url.id'], name='spu_img_ibfk_1'),
    sa.ForeignKeyConstraint(['spu_id'], ['spu.id'], name='spu_img_ibfk_2'),
    sa.PrimaryKeyConstraint('spu_id', 'img_id'),
    mysql_collate='utf8_bin',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.drop_table('spu_obj')
    # ### end Alembic commands ###
