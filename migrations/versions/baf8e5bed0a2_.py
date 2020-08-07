"""empty message

Revision ID: baf8e5bed0a2
Revises: 3ca42c78e9af
Create Date: 2020-04-25 22:10:35.344778

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'baf8e5bed0a2'
down_revision = '3ca42c78e9af'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('elements_permissions')
    op.drop_index('ix_permissions_action', table_name='permissions')
    op.drop_index('ix_permissions_name', table_name='permissions')
    op.drop_table('permissions')
    op.add_column('elements', sa.Column('permission', sa.String(length=100), nullable=True, comment='API接口权限'))
    op.create_index(op.f('ix_elements_permission'), 'elements', ['permission'], unique=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_elements_permission'), table_name='elements')
    op.drop_column('elements', 'permission')
    op.create_table('permissions',
    sa.Column('id', mysql.INTEGER(display_width=11), autoincrement=True, nullable=False),
    sa.Column('name', mysql.VARCHAR(collation='utf8_bin', length=50), nullable=True),
    sa.Column('action', mysql.VARCHAR(collation='utf8_bin', length=250), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8_bin',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_index('ix_permissions_name', 'permissions', ['name'], unique=False)
    op.create_index('ix_permissions_action', 'permissions', ['action'], unique=True)
    op.create_table('elements_permissions',
    sa.Column('element_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('permission_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('create_at', mysql.DATETIME(), nullable=True),
    sa.ForeignKeyConstraint(['element_id'], ['elements.id'], name='elements_permissions_ibfk_1'),
    sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], name='elements_permissions_ibfk_2'),
    sa.PrimaryKeyConstraint('element_id', 'permission_id'),
    mysql_collate='utf8_bin',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    # ### end Alembic commands ###
