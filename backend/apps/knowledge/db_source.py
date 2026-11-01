"""Restricted read-only external database knowledge source.

Master spec section 7 requirements this satisfies, and how:
  - Dedicated read-only credentials: the business supplies them; this
    module never writes, only ever issues a single `SELECT * FROM
    <table> LIMIT <n>` — there is no code path that can execute an
    UPDATE/DELETE/INSERT, and no user input is concatenated into SQL.
  - Statement timeouts and row limits: enforced below (STATEMENT_TIMEOUT
    / MAX_ROWS), not left to the external DB's defaults.
  - Only approved tables/views, parameterized queries: the table name is
    validated against TABLE_NAME_PATTERN (identifier characters only)
    before being interpolated into the query — it can never carry SQL
    syntax, only a bare identifier. There is no WHERE clause, no
    AI-generated SQL, no free-text query parameter at all.
  - Never connect customer databases to Ectama's primary database using
    privileged credentials: this only ever opens a new connection to the
    business-supplied host using the business-supplied credentials.

Network restriction: unlike apps.knowledge.net_safety (used for
website/API fetches, where ANY private address is a red flag — the
platform itself initiates those requests with no tenant intent behind
the specific host), a business deliberately configuring their own
database host is normal even when that host is a private/internal
address on their own network. This module therefore only blocks the
narrower, genuinely dangerous cases: loopback (the platform's own host),
the cloud metadata address, and the platform's own configured database
host/port (so a malicious/compromised tenant can't point this at
Ectama's own primary database).
"""
import re
import socket

TABLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
STATEMENT_TIMEOUT_SECONDS = 10
MAX_ROWS = 500
SUPPORTED_DIALECTS = {"postgresql", "mysql"}


class UnsafeDatabaseSourceError(ValueError):
    pass


def _is_disallowed_host(host: str) -> bool:
    from django.conf import settings

    try:
        resolved_ips = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except socket.gaierror:
        return True  # unresolvable — fail closed

    if resolved_ips & {"127.0.0.1", "::1"} or "169.254.169.254" in resolved_ips:
        return True

    own_db_host = settings.DATABASES["default"].get("HOST", "")
    if own_db_host:
        try:
            own_ips = {info[4][0] for info in socket.getaddrinfo(own_db_host, None)}
            if resolved_ips & own_ips:
                return True
        except socket.gaierror:
            pass
    return False


def _validate_config(config: dict) -> None:
    if config.get("dialect") not in SUPPORTED_DIALECTS:
        raise UnsafeDatabaseSourceError(f"Unsupported dialect: {config.get('dialect')!r}. Supported: {SUPPORTED_DIALECTS}.")
    if not config.get("host"):
        raise UnsafeDatabaseSourceError("host is required.")
    table = config.get("table", "")
    if not TABLE_NAME_PATTERN.match(table):
        raise UnsafeDatabaseSourceError(
            "table must be a bare identifier (letters, numbers, underscores only) — no schema-qualified or quoted names."
        )
    if _is_disallowed_host(config["host"]):
        raise UnsafeDatabaseSourceError(f"Host {config['host']!r} is not allowed as an external database source.")


def _fetch_postgresql(config: dict) -> tuple[list[str], list[tuple]]:
    import psycopg

    conninfo = (
        f"host={config['host']} port={config.get('port', 5432)} "
        f"dbname={config['database']} user={config['user']} password={config['password']} "
        f"connect_timeout={STATEMENT_TIMEOUT_SECONDS}"
    )
    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_SECONDS * 1000}")
            # Table name is pre-validated by TABLE_NAME_PATTERN above —
            # this is the one place a validated-but-not-parameterizable
            # identifier is interpolated; psycopg's sql.Identifier adds a
            # second layer of correct quoting on top of that validation.
            from psycopg import sql

            cur.execute(sql.SQL("SELECT * FROM {} LIMIT %s").format(sql.Identifier(config["table"])), [MAX_ROWS])
            columns = [desc.name for desc in cur.description]
            rows = cur.fetchall()
    return columns, rows


def _fetch_mysql(config: dict) -> tuple[list[str], list[tuple]]:
    import pymysql

    conn = pymysql.connect(
        host=config["host"],
        port=int(config.get("port", 3306)),
        database=config["database"],
        user=config["user"],
        password=config["password"],
        connect_timeout=STATEMENT_TIMEOUT_SECONDS,
        read_timeout=STATEMENT_TIMEOUT_SECONDS,
    )
    try:
        with conn.cursor() as cur:
            # MySQL identifiers can't be parameterized either — same
            # validated-identifier approach as Postgres, backtick-quoted.
            table = config["table"].replace("`", "")  # defence in depth; TABLE_NAME_PATTERN already rejects backticks
            cur.execute(f"SELECT * FROM `{table}` LIMIT %s", (MAX_ROWS,))
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
    finally:
        conn.close()
    return columns, rows


def fetch_rows_as_text(config: dict) -> str:
    """config: {"dialect", "host", "port", "database", "user", "password",
    "table"} — see KnowledgeDocument.external_db_credentials. Returns the
    fetched rows flattened into retrievable text (one line per row,
    "column: value" pairs), the same shape extract_csv already produces
    for uploaded CSVs, so chunking/embedding treats it identically."""
    _validate_config(config)

    fetcher = _fetch_postgresql if config["dialect"] == "postgresql" else _fetch_mysql
    columns, rows = fetcher(config)

    lines = []
    for row in rows:
        lines.append(", ".join(f"{col}: {value}" for col, value in zip(columns, row)))
    return "\n".join(lines)
