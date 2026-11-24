"""anulación de casos

Revisión: 0009
Anterior: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('casos', sa.Column('anulado_en', sa.DateTime(timezone=True), nullable=True))
    op.add_column('casos', sa.Column('anulado_por', sa.String(length=120), nullable=True))
    op.add_column('casos', sa.Column('anulado_motivo', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('casos', 'anulado_motivo')
    op.drop_column('casos', 'anulado_por')
    op.drop_column('casos', 'anulado_en')
