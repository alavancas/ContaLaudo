"""empty message

Revision ID: 726b8ccfc28c
Revises: ac5dd48a4254
Create Date: 2024-12-23 18:35:37.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '726b8ccfc28c'
down_revision = 'ac5dd48a4254'
branch_labels = None
depends_on = None


def upgrade():
    # Add tipo_remuneracao column as nullable first
    op.add_column('periodo', sa.Column('tipo_remuneracao', sa.String(length=20), nullable=True))
    
    # Update existing records
    op.execute("UPDATE periodo SET tipo_remuneracao = 'producao'")
    
    # Now make it not nullable
    op.alter_column('periodo', 'tipo_remuneracao',
               existing_type=sa.String(length=20),
               nullable=False)

    op.alter_column('procedimento', 'user_id',
               existing_type=sa.INTEGER(),
               nullable=False)


def downgrade():
    op.alter_column('procedimento', 'user_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.drop_column('periodo', 'tipo_remuneracao')
