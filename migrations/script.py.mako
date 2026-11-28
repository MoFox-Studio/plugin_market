"""${message}"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    """应用迁移。"""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """撤销迁移。"""
    ${downgrades if downgrades else "pass"}
