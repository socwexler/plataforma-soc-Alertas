"""adjuntos y evidencias de los casos

Revisión: 0007
Anterior: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('adjuntos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('caso_id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=160), nullable=False),
        sa.Column('tipo', sa.String(length=10), nullable=False),
        sa.Column('mime', sa.String(length=100), nullable=False),
        sa.Column('tamano', sa.Integer(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('ancho', sa.Integer(), nullable=True),
        sa.Column('incluir', sa.Boolean(), nullable=False),
        sa.Column('contenido', sa.LargeBinary(), nullable=False),
        sa.Column('subido_por', sa.String(length=120), nullable=False),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("tipo IN ('EVIDENCIA', 'ADJUNTO')", name='ck_adjunto_tipo'),
        sa.ForeignKeyConstraint(['caso_id'], ['casos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'))
    op.create_index(op.f('ix_adjuntos_caso_id'), 'adjuntos', ['caso_id'], unique=False)


def downgrade() -> None:
    op.drop_table('adjuntos')
