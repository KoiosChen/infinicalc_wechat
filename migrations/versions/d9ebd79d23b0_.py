"""empty message

Revision ID: d9ebd79d23b0
Revises: 5c90281ff57d
Create Date: 2020-04-11 15:36:01.189268

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'd9ebd79d23b0'
down_revision = '5c90281ff57d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('sms_sign',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=True),
    sa.Column('sign_id', sa.String(length=64), nullable=False),
    sa.Column('content', sa.String(length=140), nullable=True),
    sa.Column('create_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('sms_template', sa.Column('create_at', sa.DateTime(), nullable=True))
    op.drop_column('sms_template', 'sign_id')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('sms_template', sa.Column('sign_id', mysql.VARCHAR(collation='utf8_bin', length=64), nullable=False))
    op.drop_column('sms_template', 'create_at')
    op.drop_table('sms_sign')
    # ### end Alembic commands ###
