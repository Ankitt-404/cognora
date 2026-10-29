import os

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector

load_dotenv()


def get_conn():
    # prepare_threshold=None: no server-side prepared statements (safe behind Neon's pooler)
    conn = psycopg.connect(os.environ["DATABASE_URL"], prepare_threshold=None,
        connect_timeout=10,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=3,)
    register_vector(conn)
    return conn