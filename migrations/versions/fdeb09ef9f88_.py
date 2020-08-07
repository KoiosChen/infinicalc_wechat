"""empty message

Revision ID: fdeb09ef9f88
Revises: 6ab4445d035f
Create Date: 2020-04-13 23:49:17.667451

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'fdeb09ef9f88'
down_revision = '6ab4445d035f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('elements',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=True),
    sa.Column('icon', sa.String(length=50), nullable=True),
    sa.Column('url', sa.String(length=250), nullable=True),
    sa.Column('order', sa.SmallInteger(), nullable=True),
    sa.Column('bg_color', sa.String(length=50), nullable=True),
    sa.Column('type', sa.String(length=20), nullable=True),
    sa.Column('permission', sa.Integer(), nullable=True),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['parent_id'], ['elements.id'], ),
    sa.ForeignKeyConstraint(['permission'], ['permissions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('roles_elements',
    sa.Column('role_id', sa.Integer(), nullable=False),
    sa.Column('element_id', sa.Integer(), nullable=False),
    sa.Column('create_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['element_id'], ['elements.id'], ),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
    sa.PrimaryKeyConstraint('role_id', 'element_id')
    )
    op.drop_table('role_menu')
    op.drop_table('menu')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('menu',
    sa.Column('id', mysql.INTEGER(display_width=11), autoincrement=True, nullable=False),
    sa.Column('name', mysql.VARCHAR(collation='utf8_bin', length=50), nullable=True),
    sa.Column('icon', mysql.VARCHAR(collation='utf8_bin', length=50), nullable=True),
    sa.Column('url', mysql.VARCHAR(collation='utf8_bin', length=250), nullable=True),
    sa.Column('order', mysql.SMALLINT(display_width=6), autoincrement=False, nullable=True),
    sa.Column('bg_color', mysql.VARCHAR(collation='utf8_bin', length=50), nullable=True),
    sa.Column('type', mysql.VARCHAR(collation='utf8_bin', length=20), nullable=True),
    sa.Column('permission', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    sa.Column('parent_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['parent_id'], ['menu.id'], name='menu_ibfk_1'),
    sa.ForeignKeyConstraint(['permission'], ['permissions.id'], name='menu_ibfk_2'),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8_bin',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.create_table('role_menu',
    sa.Column('role_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('menu_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=False),
    sa.Column('create_at', mysql.DATETIME(), nullable=True),
    sa.ForeignKeyConstraint(['menu_id'], ['menu.id'], name='role_menu_ibfk_1'),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name='role_menu_ibfk_2'),
    sa.PrimaryKeyConstraint('role_id', 'menu_id'),
    mysql_collate='utf8_bin',
    mysql_default_charset='utf8',
    mysql_engine='InnoDB'
    )
    op.drop_table('roles_elements')
    op.drop_table('elements')
    # ### end Alembic commands ###
