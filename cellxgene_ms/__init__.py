__version__ = "0.0.0"

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from collections import defaultdict as dd
import json
from cellxgene_ms.config import get_config
from cellxgene_ms.db import init_app

socketio = SocketIO()


def create_app(*args) -> Flask:
    """
    Creates app, configures it, and returns it.
    Parameters
    ----------
    args
        Path to files containing environment variables that should be loaded.

    Returns
    -------
    Flask
        Flask app.
    """

    app = Flask(__name__,
                template_folder="/home/lex/projects/cellxgene_ms/templates/")
    init_app(app)
    if len(args) == 0:
        app.config |= get_config(".env")
    else:
        app.config |= get_config(*args)

    import cellxlocal
    app.register_blueprint(cellxlocal.bp)

    socketio.init_app(app)
    return app
