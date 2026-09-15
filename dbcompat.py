import os, re, sqlite3 as _sqlite3

DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL') or os.getenv('POSTGRESQL_URL')

if DATABASE_URL:
    import psycopg
    from psycopg.rows import dict_row

    class Row(dict):
        def __getitem__(self, key):
            if isinstance(key, int):
                return list(self.values())[key]
            return super().__getitem__(key)

    class Cursor:
        def __init__(self, cur): self._cur = cur
        def _sql(self, sql):
            sql = sql.replace('INSERT OR IGNORE', 'INSERT')
            if 'INSERT INTO' in sql and 'ON CONFLICT' not in sql and sql.lstrip().upper().startswith('INSERT'):
                sql = sql + ' ON CONFLICT DO NOTHING'
            return sql.replace('?', '%s')
        def execute(self, sql, params=()):
            self._cur.execute(self._sql(sql), params); return self
        def executemany(self, sql, seq):
            self._cur.executemany(self._sql(sql), seq); return self
        def executescript(self, script):
            for stmt in script.split(';'):
                stmt=stmt.strip()
                if not stmt: continue
                stmt=re.sub(r'INTEGER PRIMARY KEY AUTOINCREMENT', 'BIGSERIAL PRIMARY KEY', stmt, flags=re.I)
                self.execute(stmt)
            return self
        def fetchone(self):
            r=self._cur.fetchone()
            return None if r is None else Row(r)
        def fetchall(self):
            return [Row(r) for r in self._cur.fetchall()]
        @property
        def lastrowid(self):
            try:
                self._cur.execute('SELECT LASTVAL()')
                return self._cur.fetchone()[0]
            except Exception:
                return None
        def __iter__(self): return iter(self.fetchall())

    class Connection:
        def __init__(self): self._con=psycopg.connect(DATABASE_URL, row_factory=dict_row)
        def cursor(self): return Cursor(self._con.cursor())
        def execute(self, sql, params=()): return self.cursor().execute(sql, params)
        def commit(self): self._con.commit()
        def close(self): self._con.close()

    def connect(_path=None): return Connection()
    Row = Row
    OperationalError = psycopg.OperationalError
    IntegrityError = psycopg.IntegrityError
else:
    connect = _sqlite3.connect
    Row = _sqlite3.Row
    OperationalError = _sqlite3.OperationalError
    IntegrityError = _sqlite3.IntegrityError
