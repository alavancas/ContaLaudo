"""add tipo_remuneracao field

Revision ID: add_tipo_remuneracao
Revises: None
Create Date: 2024-12-23 18:35:37.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_tipo_remuneracao'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add tipo_remuneracao column with a default value for existing records
    op.add_column('periodo', sa.Column('tipo_remuneracao', sa.String(20), nullable=True))
    
    # Update existing records to have 'producao' as the default tipo_remuneracao
    op.execute("UPDATE periodo SET tipo_remuneracao = 'producao' WHERE tipo_remuneracao IS NULL")
    
    # Make the column not nullable after setting default values
    op.alter_column('periodo', 'tipo_remuneracao',
                    existing_type=sa.String(20),
                    nullable=False)


def downgrade():
    op.drop_column('periodo', 'tipo_remuneracao')
