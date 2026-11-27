"""carpeta del cliente en SharePoint (anexos del informe)

Revisión: 0015
Anterior: 0014
"""
from alembic import op
import sqlalchemy as sa

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Vacío = la subcarpeta se llama como el código del cliente
    op.add_column('clientes', sa.Column('sharepoint_carpeta', sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column('clientes', 'sharepoint_carpeta')
