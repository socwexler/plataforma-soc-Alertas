"""roles N3, Líder y CISO; revisión de casos N1

Revisión: 0005
Anterior: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('ck_usuario_rol', 'usuarios', type_='check')
    op.execute("UPDATE usuarios SET rol = 'LIDER' WHERE rol = 'COORDINADOR'")
    op.create_check_constraint('ck_usuario_rol', 'usuarios', "rol IN ('N1', 'N2', 'N3', 'LIDER', 'CISO', 'ADMIN')")
    op.add_column('casos', sa.Column('revision', sa.String(length=10), nullable=True))
    op.add_column('casos', sa.Column('revisado_por', sa.String(length=120), nullable=True))
    op.add_column('casos', sa.Column('revisado_en', sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint('ck_caso_revision', 'casos',
                               "revision IS NULL OR revision IN ('PENDIENTE', 'REVISADO', 'OBSERVADO')")
    op.create_index(op.f('ix_casos_revision'), 'casos', ['revision'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_casos_revision'), table_name='casos')
    op.drop_constraint('ck_caso_revision', 'casos', type_='check')
    for col in ('revisado_en', 'revisado_por', 'revision'):
        op.drop_column('casos', col)
    op.drop_constraint('ck_usuario_rol', 'usuarios', type_='check')
    op.execute("UPDATE usuarios SET rol = 'COORDINADOR' WHERE rol = 'LIDER'")
    op.execute("UPDATE usuarios SET rol = 'N2' WHERE rol = 'N3'")
    # el rol de solo lectura no existe en la versión anterior: se desactiva en vez de darle más permisos
    op.execute("UPDATE usuarios SET rol = 'N1', activo = false WHERE rol = 'CISO'")
    op.create_check_constraint('ck_usuario_rol', 'usuarios', "rol IN ('N1', 'N2', 'COORDINADOR', 'ADMIN')")
