"""evidencias de la gestión (cambio de estado del caso)

Revisión: 0013
Anterior: 0012
"""
from alembic import op
import sqlalchemy as sa

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('adjuntos', sa.Column('seguimiento_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_adjunto_seguimiento', 'adjuntos', 'seguimientos', ['seguimiento_id'], ['id'], ondelete='SET NULL')
    op.drop_constraint('ck_adjunto_tipo', 'adjuntos', type_='check')
    op.create_check_constraint('ck_adjunto_tipo', 'adjuntos', "tipo IN ('EVIDENCIA', 'ADJUNTO', 'GESTION')")
    op.create_check_constraint('ck_adjunto_gestion', 'adjuntos', "tipo <> 'GESTION' OR NOT incluir")


def downgrade() -> None:
    # los archivos se conservan, como adjuntos que no van en el correo
    op.execute("UPDATE adjuntos SET tipo = 'ADJUNTO' WHERE tipo = 'GESTION'")
    op.drop_constraint('ck_adjunto_gestion', 'adjuntos', type_='check')
    op.drop_constraint('ck_adjunto_tipo', 'adjuntos', type_='check')
    op.create_check_constraint('ck_adjunto_tipo', 'adjuntos', "tipo IN ('EVIDENCIA', 'ADJUNTO')")
    op.drop_constraint('fk_adjunto_seguimiento', 'adjuntos', type_='foreignkey')
    op.drop_column('adjuntos', 'seguimiento_id')
