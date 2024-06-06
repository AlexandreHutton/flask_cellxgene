import sqlite3
from flask import current_app, g
import os
import click


def get_db():
    """
    Gets the DB for the currently-running app.
    Returns
    -------

    """
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE_PATH"],
                               detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON;")
    return g.db


def close_db(e=None):
    """Closes the db"""
    db = g.pop("db", None)
    if db is not None:
        db.close()
    return


def init_db():
    if os.path.exists(current_app.config["DATABASE_PATH"]):
        raise ValueError(f"Database already exists at: {current_app.config['DATABASE_PATH']}")
    db = get_db()
    with current_app.open_resource(current_app.config["SQL_SCHEMA_PATH"]) as f:
        db.executescript(f.read().decode("utf8"))
    return


@click.command("init-db")
def init_db_command():
    init_db()
    click.echo("Database initialized.")
    return


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    return
