import os
import django
from urllib.parse import urlparse

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'payplan.settings')
django.setup()

from django.conf import settings
import psycopg2

# Connect to the postgres maintenance database instead
url = urlparse(os.getenv('DATABASE_URL', ''))
conn = psycopg2.connect(
    dbname='postgres',
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=5432,
)
conn.set_session(autocommit=True)
cursor = conn.cursor()
cursor.execute("""
    SELECT pg_terminate_backend(pg_stat_activity.pid)
    FROM pg_stat_activity
    WHERE pg_stat_activity.datname = 'test_neondb'
      AND pid <> pg_backend_pid()
""")
cursor.execute("DROP DATABASE IF EXISTS test_neondb")
print("Done - test_neondb dropped")
