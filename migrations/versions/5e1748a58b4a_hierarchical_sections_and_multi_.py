"""hierarchical_sections_and_multi_fragment_links

Revision ID: 5e1748a58b4a
Revises: 8793c7031ee3
Create Date: 2026-11-16 10:41:42.270879

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e1748a58b4a'
down_revision: Union[str, Sequence[str], None] = '8793c7031ee3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('compilation_fragments', schema=None) as batch_op:
        batch_op.drop_constraint('uq_compilation_fragment', type_='unique')
        batch_op.create_unique_constraint(
            'uq_compilation_section_fragment',
            ['compilation_id', 'section_id', 'fragment_id']
        )

    with op.batch_alter_table('compilation_sections', schema=None) as batch_op:
        batch_op.add_column(sa.Column('parent_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_compilation_sections_parent_id',
            'compilation_sections',
            ['parent_id'],
            ['id'],
            ondelete='CASCADE'
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('compilation_sections', schema=None) as batch_op:
        batch_op.drop_constraint('fk_compilation_sections_parent_id', type_='foreignkey')
        batch_op.drop_column('parent_id')

    with op.batch_alter_table('compilation_fragments', schema=None) as batch_op:
        batch_op.drop_constraint('uq_compilation_section_fragment', type_='unique')
        batch_op.create_unique_constraint('uq_compilation_fragment', ['compilation_id', 'fragment_id'])
