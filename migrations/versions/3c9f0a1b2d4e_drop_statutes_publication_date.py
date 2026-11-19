"""drop obsolete statutes.publication_date

Revision ID: 3c9f0a1b2d4e
Revises: 5e1748a58b4a
Create Date: 2026-11-19

A coluna ``statutes.publication_date`` existia no esquema inicial, mas não
integra mais o modelo ``Statute``. As rotinas de adoção legada a recriavam
indevidamente; esta revisão a remove de forma idempotente (SQLite exige
batch mode para DROP COLUMN em versões antigas).
"""

from alembic import op
import sqlalchemy as sa


revision = '3c9f0a1b2d4e'
down_revision = '5e1748a58b4a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'statutes' not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns('statutes')}
    if 'publication_date' in columns:
        with op.batch_alter_table('statutes') as batch:
            batch.drop_column('publication_date')


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'statutes' not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns('statutes')}
    if 'publication_date' not in columns:
        with op.batch_alter_table('statutes') as batch:
            batch.add_column(sa.Column('publication_date', sa.Date(), nullable=True))
