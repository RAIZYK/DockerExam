import os
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://marketuser:marketpass@db:5432/marketdb")
def connect():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=5)
