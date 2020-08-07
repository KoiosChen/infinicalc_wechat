"""empty message

Revision ID: 676badbadf54
Revises: fdeb09ef9f88
Create Date: 2020-04-14 07:54:39.024815

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '676badbadf54'
down_revision = 'fdeb09ef9f88'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('elements_permissions',
    sa.Column('element_id', sa.Integer(), nullable=False),
    sa.Column('permission_id', sa.Integer(), nullable=False),
    sa.Column('create_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['element_id'], ['elements.id'], ),
    sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ),
    sa.PrimaryKeyConstraint('element_id', 'permission_id')
    )
    op.drop_constraint('elements_ibfk_2', 'elements', type_='foreignkey')
    op.drop_column('elements', 'permission')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('elements', sa.Column('permission', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True))
    op.create_foreign_key('elements_ibfk_2', 'elements', 'permissions', ['permission'], ['id'])
    op.drop_table('elements_permissions')
    # ### end Alembic commands ###
