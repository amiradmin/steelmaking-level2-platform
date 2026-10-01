"""Database migration for historian query-performance indexes."""

from django.db import migrations


REAL_S7_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS ix_process_samples_real_s7_good_tag_ts
ON process_samples(tag_id, ts DESC)
WHERE quality = 'GOOD'
  AND attributes ->> 'source_kind' = 'REAL_S7';
"""

DROP_REAL_S7_INDEX_SQL = """
DROP INDEX IF EXISTS ix_process_samples_real_s7_good_tag_ts;
"""


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.RunSQL(
            sql=REAL_S7_INDEX_SQL,
            reverse_sql=DROP_REAL_S7_INDEX_SQL,
        ),
    ]
