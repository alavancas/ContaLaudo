"""Adiciona coluna user_id na tabela procedimentos

Revision ID: add_user_id_to_procedimentos
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Adiciona a coluna user_id
    op.add_column('procedimento', sa.Column('user_id', sa.Integer(), nullable=True))
    
    # Adiciona a foreign key
    op.create_foreign_key(
        'fk_procedimento_user_id', 'procedimento', 'user',
        ['user_id'], ['id']
    )
    
    # Marca a coluna como não nula após a migração
    op.alter_column('procedimento', 'user_id',
                    existing_type=sa.Integer(),
                    nullable=False)

def downgrade():
    # Remove a foreign key
    op.drop_constraint('fk_procedimento_user_id', 'procedimento', type_='foreignkey')
    
    # Remove a coluna
    op.drop_column('procedimento', 'user_id')
