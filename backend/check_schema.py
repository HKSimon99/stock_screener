"""Quick DB schema verification script — delete after use."""
import psycopg2
from app.core.config import settings

url = settings.sync_database_url.replace("+psycopg2", "")
conn = psycopg2.connect(url)
cur = conn.cursor()

cur.execute(
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema = %s ORDER BY table_name",
    ("consensus_app",),
)
rows = cur.fetchall()
print("Tables in consensus_app:")
for r in rows:
    print(" -", r[0])

# Also check if alembic_version is there
cur.execute(
    "SELECT version_num FROM consensus_app.alembic_version"
    if rows else "SELECT 'no tables yet'"
)
try:
    print("Alembic version:", cur.fetchone())
except Exception as e:
    print("Alembic version error:", e)

conn.close()
