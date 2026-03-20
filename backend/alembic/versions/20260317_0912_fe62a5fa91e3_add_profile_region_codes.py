"""add_profile_region_codes

Revision ID: fe62a5fa91e3
Revises: 20260313_0002
Create Date: 2026-03-17 09:12:15.831356+00:00

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fe62a5fa91e3"
down_revision: Union[str, Sequence[str], None] = "20260313_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "profiles",
        sa.Column(
            "region_country_code",
            sa.String(length=2),
            nullable=True,
            comment="Region country/territory code (ISO 3166-1 alpha-2, e.g. CN/HK/MO/TW)",
        ),
    )
    op.add_column(
        "profiles",
        sa.Column(
            "region_cn_city_code",
            sa.String(length=6),
            nullable=True,
            comment="CN city-level administrative division code (6 digits), only when region_country_code=CN",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("profiles", "region_cn_city_code")
    op.drop_column("profiles", "region_country_code")
