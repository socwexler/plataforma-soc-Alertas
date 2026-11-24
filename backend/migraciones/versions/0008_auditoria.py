"""registro de cambios administrativos

Revisión: 0008
Anterior: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('auditoria',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('usuario', sa.String(length=200), nullable=False),
        sa.Column('accion', sa.String(length=20), nullable=False),
        sa.Column('objeto', sa.String(length=400), nullable=False),
        sa.Column('detalle', sa.Text(), nullable=True),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'))
    op.create_index(op.f('ix_auditoria_creado_en'), 'auditoria', ['creado_en'], unique=False)


def downgrade() -> None:
    op.drop_table('auditoria')
