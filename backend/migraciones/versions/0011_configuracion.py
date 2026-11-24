"""configuración administrable, conexiones, claves de acceso y avisos internos

Revisión: 0011
Anterior: 0010
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    fecha = sa.DateTime(timezone=True)
    op.create_table('configuracion',
        sa.Column('clave', sa.String(length=60), nullable=False),
        sa.Column('valor', sa.Text(), nullable=True),
        sa.Column('por', sa.String(length=120), nullable=False),
        sa.Column('en', fecha, nullable=False),
        sa.PrimaryKeyConstraint('clave'))
    op.create_table('conexiones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=80), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('autenticacion', sa.String(length=10), nullable=False),
        sa.Column('cabecera', sa.String(length=60), nullable=True),
        sa.Column('usuario', sa.String(length=120), nullable=True),
        sa.Column('clave', sa.Text(), nullable=True),
        sa.Column('notas', sa.String(length=500), nullable=True),
        sa.Column('activo', sa.Boolean(), nullable=False),
        sa.Column('por', sa.String(length=120), nullable=False),
        sa.Column('en', fecha, nullable=False),
        sa.PrimaryKeyConstraint('id'), sa.UniqueConstraint('nombre'))
    op.create_table('claves_api',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=80), nullable=False),
        sa.Column('prefijo', sa.String(length=12), nullable=False),
        sa.Column('huella', sa.String(length=64), nullable=False),
        sa.Column('permisos', postgresql.JSONB(), nullable=False),
        sa.Column('cliente_id', sa.Integer(), nullable=True),
        sa.Column('vence_en', fecha, nullable=False),
        sa.Column('revocada_en', fecha, nullable=True),
        sa.Column('ultimo_uso', fecha, nullable=True),
        sa.Column('creada_por', sa.String(length=120), nullable=False),
        sa.Column('creado_en', fecha, server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['cliente_id'], ['clientes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'), sa.UniqueConstraint('huella'))
    op.create_table('avisos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=20), nullable=False),
        sa.Column('asunto', sa.String(length=250), nullable=False),
        sa.Column('cuerpo', sa.Text(), nullable=False),
        sa.Column('para', postgresql.JSONB(), nullable=False),
        sa.Column('estado', sa.String(length=12), nullable=False),
        sa.Column('intentos', sa.Integer(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('proximo', fecha, nullable=False),
        sa.Column('creado_en', fecha, server_default=sa.text('now()'), nullable=False),
        sa.Column('enviado_en', fecha, nullable=True),
        sa.CheckConstraint("estado IN ('PENDIENTE', 'ENVIADO', 'ERROR', 'DESCARTADO')", name='ck_aviso_estado'),
        sa.PrimaryKeyConstraint('id'))
    op.create_index(op.f('ix_avisos_estado'), 'avisos', ['estado'], unique=False)


def downgrade() -> None:
    for t in ('avisos', 'claves_api', 'conexiones', 'configuracion'):
        op.drop_table(t)
