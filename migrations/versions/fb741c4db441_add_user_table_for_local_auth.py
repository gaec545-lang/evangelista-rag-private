"""Add User table for local auth

Revision ID: fb741c4db441
Revises: 93ba2028938c
Create Date: 2026-06-17 12:22:35.394930

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid


# revision identifiers, used by Alembic.
revision: str = 'fb741c4db441'
down_revision: Union[str, Sequence[str], None] = '93ba2028938c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    usuarios_table = op.create_table('usuarios',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('rol', sa.String(), server_default='socio', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(op.f('ix_usuarios_email'), 'usuarios', ['email'], unique=True)
    
    op.bulk_insert(
        usuarios_table,
        [
            {
                'id': uuid.uuid4(),
                'email': 'direccion@evangelistaco.com',
                'hashed_password': '$2b$12$hqNWr5qSpWXERoUS.1FfgORsj3ZhkEE1e5N.e178rX4alKLNZmtkW',
                'rol': 'socio'
            }
        ]
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_usuarios_email'), table_name='usuarios')
    op.drop_table('usuarios')
