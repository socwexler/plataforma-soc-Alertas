"""alertas por tratar: tickets que el SIEM crea en GLPI

Revisión: 0014
Anterior: 0013
"""
from alembic import op
import sqlalchemy as sa

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'alertas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('glpi_ticket_id', sa.Integer(), nullable=False),
        sa.Column('glpi_entidad_id', sa.Integer(), nullable=True),
        sa.Column('glpi_estado', sa.Integer(), nullable=True),
        sa.Column('cliente_id', sa.Integer(), nullable=True),
        sa.Column('titulo', sa.Text(), nullable=False),
        sa.Column('contenido', sa.Text(), nullable=True),
        sa.Column('criticidad', sa.String(length=10), nullable=True),
        sa.Column('fecha_alerta', sa.DateTime(timezone=True), nullable=False),
        sa.Column('estado', sa.String(length=14), nullable=False),
        sa.Column('analista_id', sa.Integer(), nullable=True),
        sa.Column('tomada_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('caso_id', sa.Integer(), nullable=True),
        sa.Column('reportada_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cerrada_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('avisada_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('importada_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("estado IN ('POR_REPORTAR', 'EN_GESTION', 'REPORTADA', 'CERRADA_GLPI')", name='ck_alerta_estado'),
        sa.CheckConstraint("criticidad IS NULL OR criticidad IN ('Crítica', 'Alta', 'Media', 'Baja')", name='ck_alerta_criticidad'),
        sa.CheckConstraint("estado <> 'REPORTADA' OR caso_id IS NOT NULL", name='ck_alerta_reportada'),
        sa.ForeignKeyConstraint(['analista_id'], ['usuarios.id']),
        sa.ForeignKeyConstraint(['caso_id'], ['casos.id']),
        sa.ForeignKeyConstraint(['cliente_id'], ['clientes.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('caso_id'),
        sa.UniqueConstraint('glpi_ticket_id'),
    )
    op.create_index(op.f('ix_alertas_estado'), 'alertas', ['estado'], unique=False)
    op.create_index(op.f('ix_alertas_cliente_id'), 'alertas', ['cliente_id'], unique=False)


def downgrade() -> None:
    # Los casos ya reportados conservan su ticket; solo se pierde la bandeja
    op.drop_index(op.f('ix_alertas_cliente_id'), table_name='alertas')
    op.drop_index(op.f('ix_alertas_estado'), table_name='alertas')
    op.drop_table('alertas')
