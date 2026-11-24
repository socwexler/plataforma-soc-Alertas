"""destinatarios del correo de alerta por cliente

Revisión: 0006
Anterior: 0005
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    for col in ('correos_para', 'correos_cc', 'correos_dominios'):
        op.add_column('clientes', sa.Column(col, postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False))
    op.add_column('clientes', sa.Column('correos_por', sa.String(length=120), nullable=True))
    op.add_column('clientes', sa.Column('correos_en', sa.DateTime(timezone=True), nullable=True))
    # Lo que hubiera en el campo anterior se conserva, pero queda bloqueado hasta que se definan los dominios
    op.execute(r"""
        UPDATE clientes SET correos_para = to_jsonb(array_remove(regexp_split_to_array(lower(trim(correos_notificacion)), '[;,\s]+'), ''))
        WHERE coalesce(trim(correos_notificacion), '') <> ''
    """)
    op.drop_column('clientes', 'correos_notificacion')


def downgrade() -> None:
    op.add_column('clientes', sa.Column('correos_notificacion', sa.Text(), nullable=True))
    op.execute("""UPDATE clientes SET correos_notificacion = (SELECT string_agg(x, ', ') FROM jsonb_array_elements_text(correos_para) x)
                  WHERE jsonb_array_length(correos_para) > 0""")
    for col in ('correos_en', 'correos_por', 'correos_dominios', 'correos_cc', 'correos_para'):
        op.drop_column('clientes', col)
