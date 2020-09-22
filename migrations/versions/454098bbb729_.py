"""empty message

Revision ID: 454098bbb729
Revises: 
Create Date: 2020-08-26 21:25:48.678798

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '454098bbb729'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('news_center',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('title', sa.String(length=30), nullable=True, comment='主标题'),
    sa.Column('sub_title', sa.String(length=30), nullable=True, comment='副标题'),
    sa.Column('cover_image', sa.String(length=64), nullable=True),
    sa.Column('content', sa.Text(length=4294967295), nullable=True, comment='富文本，sku描述'),
    sa.Column('order', sa.SmallInteger(), nullable=True, comment='文章排序'),
    sa.Column('create_at', sa.DateTime(), nullable=True),
    sa.Column('update_at', sa.DateTime(), nullable=True),
    sa.Column('delete_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['cover_image'], ['obj_storage.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('news_sections',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=True),
    sa.Column('section_image', sa.String(length=64), nullable=True),
    sa.Column('order', sa.SmallInteger(), nullable=True, comment='栏目排序'),
    sa.Column('create_at', sa.DateTime(), nullable=True),
    sa.Column('update_at', sa.DateTime(), nullable=True),
    sa.Column('delete_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['section_image'], ['obj_storage.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('news_sections')
    op.drop_table('news_center')
    # ### end Alembic commands ###