import psycopg2
from contextlib import contextmanager
from psycopg2.extras import RealDictCursor

from backend.app_config import POSTGRES_DATABASE_URL


POSTGRES_AVAILABLE = True


def get_connection():
    try:
        return psycopg2.connect(
            POSTGRES_DATABASE_URL,
            connect_timeout=5  
        )
    except Exception as e:
        global POSTGRES_AVAILABLE
        POSTGRES_AVAILABLE = False
        print(f"Postgres connection failed: {e}")
        return None


class PostgresClient:
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()

    def execute_query(self, query, params=None, fetch=False, dict_cursor=False):
        try:
            cursor = self.conn.cursor(cursor_factory=RealDictCursor) if dict_cursor else self.cursor

            cursor.execute(query, params)

            if fetch:
                return cursor.fetchall()

            return None

        except Exception as e:
            print(f"Query failed: {e}")
            return None
        
    def insert_record(self, table, record: dict, upsert_key: str = None):
        try:
            columns = record.keys()
            values = list(record.values())

            placeholders = ", ".join(["%s"] * len(values))
            column_names = ", ".join(columns)

            if upsert_key:
                update_clause = ", ".join(
                    [f"{col}=EXCLUDED.{col}" for col in columns if col != upsert_key]
                )

                query = f"""
                INSERT INTO {table} ({column_names})
                VALUES ({placeholders})
                ON CONFLICT ({upsert_key})
                DO UPDATE SET {update_clause}
                """
            else:
                query = f"""
                INSERT INTO {table} ({column_names})
                VALUES ({placeholders})
                """

            self.cursor.execute(query, values)
            self.conn.commit()
            return True

        except Exception as e:
            print(f"Insert failed: {e}")
            self.conn.rollback()
            return False

    def ensure_table_exists(self, create_sql: str):
        try:
            self.cursor.execute(create_sql)
            self.conn.commit()
        except Exception as e:
            print(f"Table creation failed: {e}")
            self.conn.rollback()

    def commit(self):
        self.conn.commit()

    def close(self):
        try:
            self.cursor.close()
            self.conn.close()
        except Exception as e:
            print(f"Error closing DB connection: {e}")


@contextmanager
def connection_scoped_client():
    conn = get_connection()

    if not conn:
        yield None
        return

    client = PostgresClient(conn)

    try:
        yield client
    finally:
        client.close()