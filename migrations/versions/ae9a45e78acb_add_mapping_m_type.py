"""Add Mapping.m_type

Revision ID: ae9a45e78acb
Revises: 3800cbc28f7e
Create Date: 2020-06-15 11:36:49.712790

"""
from alembic import op
import sqlalchemy as sa
from app.models import Mapping


# revision identifiers, used by Alembic.
revision = 'ae9a45e78acb'
down_revision = '3800cbc28f7e'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('mapping', sa.Column('m_type',
        sa.Enum('automatic', 'manual', name='mappingtypes',
            create_constraint=False)
        , nullable=True))

    # Populate m_type for all existing mappings default to manual
    bind = op.get_bind()
    session = sa.orm.Session(bind=bind)
    mappings = session.query(Mapping)
    num_mappings = len(list(mappings))
    if num_mappings > 0:
        print("Setting m_type to 'manual' for all %d mappings" % num_mappings)
        for m in mappings:
            m.m_type = "manual"
    session.commit()


def downgrade():
    # Deleting a column in SQLite has us go through Batch mode instead of:
    # op.drop_column('mapping', 'type')
    with op.batch_alter_table("mapping") as batch_op:
        batch_op.drop_column('m_type')
