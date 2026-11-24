"""actividades y pendientes del informe

Revisión: 0012
Anterior: 0011
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('informes', sa.Column('actividades', postgresql.JSONB(), server_default='[]', nullable=False))


def downgrade() -> None:
    op.drop_column('informes', 'actividades')
