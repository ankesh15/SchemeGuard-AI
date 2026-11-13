"""Run with migration-owner credentials; runtime secrets are environment-only."""

import os
import re

import psycopg
from psycopg import sql

from app.core.config import get_settings


def main() -> None:
    role = os.environ["RUNTIME_DATABASE_USER"]
    password = os.environ["RUNTIME_DATABASE_PASSWORD"]
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,62}", role) or len(password) < 24:
        raise SystemExit("Use a simple runtime role and a random password of at least 24 characters")
    settings = get_settings()
    with psycopg.connect(settings.psycopg_dsn) as connection:
        owner = connection.execute("SELECT current_user").fetchone()
        if owner and owner[0] == role:
            raise SystemExit("Runtime role must differ from the migration owner")
        exists = connection.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone()
        if not exists:
            connection.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION"
                ).format(sql.Identifier(role), sql.Literal(password))
            )
        flags = connection.execute(
            "SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls FROM pg_roles WHERE rolname=%s",
            (role,),
        ).fetchone()
        member = connection.execute("SELECT pg_has_role(%s,current_user,'MEMBER')", (role,)).fetchone()
        if (flags and flags[0]) or (member and member[0]):
            raise SystemExit(
                "Refusing privileged or owner-member runtime role; choose a distinct restricted account"
            )
        # Existing role passwords are deliberately preserved; rotate separately.
        database = settings.sqlalchemy_url.database
        connection.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(str(database)), sql.Identifier(role)
            )
        )
        for schema in ("public", "sg_checkpoints"):
            connection.execute(
                sql.SQL("REVOKE CREATE ON SCHEMA {} FROM PUBLIC").format(sql.Identifier(schema))
            )
            connection.execute(
                sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(schema), sql.Identifier(role))
            )
            connection.execute(
                sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {} TO {}").format(
                    sql.Identifier(schema), sql.Identifier(role)
                )
            )
            connection.execute(
                sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}").format(
                    sql.Identifier(schema), sql.Identifier(role)
                )
            )
            connection.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
                ).format(sql.Identifier(schema), sql.Identifier(role))
            )
        connection.execute(
            sql.SQL("REVOKE UPDATE, DELETE ON audit_events FROM {}").format(sql.Identifier(role))
        )
    print(
        "Runtime DML grants configured; owner credentials and existing role password were not printed or changed"
    )


if __name__ == "__main__":
    main()
