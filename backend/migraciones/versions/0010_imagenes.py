"""logo de clientes e imágenes de boletines

Revisión: 0010
Anterior: 0009
"""
from alembic import op
import sqlalchemy as sa

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('clientes', sa.Column('logo', sa.LargeBinary(), nullable=True))
    op.add_column('clientes', sa.Column('logo_mime', sa.String(length=20), nullable=True))
    op.add_column('clientes', sa.Column('logo_claro', sa.Boolean(), nullable=True))
    op.create_table('informe_imagenes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('informe_id', sa.Integer(), nullable=False),
        sa.Column('mime', sa.String(length=20), nullable=False),
        sa.Column('ancho', sa.Integer(), nullable=False),
        sa.Column('alto', sa.Integer(), nullable=False),
        sa.Column('contenido', sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(['informe_id'], ['informes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'))
    op.create_index(op.f('ix_informe_imagenes_informe_id'), 'informe_imagenes', ['informe_id'], unique=False)


def downgrade() -> None:
    op.drop_table('informe_imagenes')
    op.drop_column('clientes', 'logo_claro')
    op.drop_column('clientes', 'logo_mime')
    op.drop_column('clientes', 'logo')
