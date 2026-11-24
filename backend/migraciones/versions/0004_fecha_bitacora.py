"""fecha de la bitácora en casos

Revisión: 0004
Anterior: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('casos', sa.Column('fecha_bitacora', sa.Date(), nullable=True))
    # En lo importado antes de esta versión, el día de fecha_evento siempre era la columna "Fecha" del Excel
    op.execute("""
        UPDATE casos SET fecha_bitacora = (CASE WHEN origen = 'migracion' THEN fecha_evento
            ELSE coalesce(fecha_reporte, fecha_evento) END AT TIME ZONE 'America/Bogota')::date
    """)
    op.create_index(op.f('ix_casos_fecha_bitacora'), 'casos', ['fecha_bitacora'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_casos_fecha_bitacora'), table_name='casos')
    op.drop_column('casos', 'fecha_bitacora')
