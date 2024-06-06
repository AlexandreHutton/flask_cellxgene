from flask import Flask, redirect, current_app, render_template, request, flash
from flask.blueprints import Blueprint
import subprocess
import requests
import time
from cellxgene_ms import socketio
import random
from flask import jsonify
from cellxgene_ms.db import get_db
from sqlite3 import IntegrityError
from os.path import basename, dirname

bp = Blueprint("cellxgene", __name__, url_prefix="/cxg/")


@bp.route("/request_cxg_port", methods=["GET", "POST"])
def request_cxg_port():
    if request.method == "POST":
        # Need the user id from request
        id_user = request.json["id_user"]
        db = get_db()

        # Release previously-reserved port, if any
        release_port(db, id_user)

        request_successful = request_available_port(db, id_user)
        if not request_successful:
            return jsonify({"success": False, "message": "Unable to reserve port."})
        if request_successful:
            port = assign_port(db, id_user)
        return jsonify({"success": True, "message": "", "port": port})


@bp.route("/get_cxg_port", methods=["POST"])
def get_cxg_port():
    """Returns the port associated with a user, if any."""
    id_user = request.json["id_user"]
    db = get_db()
    port = get_assigned_port(db, id_user)
    return jsonify({"port": port})


@bp.route("/cellxgene", methods=["POST"])
def start_cellxgene():
    """Starts a CellXGene container if a port has been successfully reserved."""
    # Warning: This should not be front facing. It should only be interacted with via an intermediary that passes
    # sanitized data via a POST request.
    if request.method == "POST":
        id_user = request.json["id_user"]
        file_dir = dirname(request.json["filepath"])
        file_name = basename(request.json["filepath"])

        db = get_db()
        port = get_assigned_port(db, id_user)
        if port is None:
            flash("Port reservation failed. Try again or report the problem to site admins.")
            return redirect("/")
        command = ["docker", "run", "-v", f"{file_dir}:/data/:ro", "-p", f"{port}:5005", "cellxgene",
                   "launch", "--host", "0.0.0.0", f"/data/{file_name}", "--disable-diffexp", "--disable-annotations"]
        p = subprocess.Popen(command)
        attempt_counter = 0
        while True:
            try:
                response = requests.get(f"http://localhost:{port}")
                if response.status_code == 200:
                    break
            except requests.ConnectionError:
                pass
            time.sleep(1)
            attempt_counter += 1
            if attempt_counter >= current_app.config["MAX_START_ATTEMPTS"]:
                flash("Failed to start CellXGene. Please try again later.")
                release_port(db, id_user)
                return jsonify({"success": False, "message": "Unable to connect to CellXGene instance on startup."}), 500
        register_session(db, id_user, port)
        return jsonify({"success": True, "message": "", "port": port})


def register_session(db, id_user, port):
    """Registers that a Docker container for the user is running."""
    db.execute("INSERT INTO running_container (id_user, port) VALUES (?,?)", (id_user, port))
    db.commit()
    return


def get_docker_id(port: str) -> str:
    return subprocess.check_output(["docker", "ps", "-q", "--filter", f"publish={port}"]).decode().strip()


@bp.route("/release_port", methods=["POST"])
def request_port_release():
    db = get_db()
    port = release_port(db, request.json["id_user"])
    print(f"Port {port} released.")
    return jsonify({"success": True}), 200


def release_port(db, id_user):
    """Releases any requests, reservations, and Docker containers associated with the specified user."""
    # Kill docker container running on that port, if any
    port = get_assigned_port(db, id_user)
    if port is None:
        return
    stop_docker_at_port(port)
    # Remove any reservation
    db.execute("DELETE FROM assigned_port WHERE id_user = ?", (id_user,))
    db.execute("DELETE FROM port_reservation WHERE id_user = ?", (id_user,))
    db.execute("DELETE FROM running_container WHERE id_user = ?", (id_user,))
    db.commit()
    return port


def stop_docker_at_port(port):
    """Stops the Docker container running at the specified port."""
    docker_id = get_docker_id(port)
    if docker_id is None or len(docker_id) == 0:
        return
    subprocess.check_call(["docker", "stop", docker_id])  # print( prints out the ID of the container being stopped
    return


def get_assigned_port(db, id_user):
    port_info = db.execute("SELECT port FROM assigned_port WHERE id_user = ?", (id_user,)).fetchone()
    if port_info is None:
        port_info = db.execute("SELECT requested_port FROM port_reservation WHERE id_user = ?", (id_user,)).fetchone()
    if port_info is None:
        port_info = db.execute("SELECT port FROM running_container WHERE id_user = ?", (id_user,)).fetchone()
    if port_info is None:
        return None
    if "port" in dict(port_info):
        return port_info["port"]
    else:
        return port_info["requested_port"]


def assign_port(db, id_user):
    """Assigns a reserved port to the connection."""
    # Get from DB and assign port
    port_info = db.execute("SELECT requested_port FROM port_reservation WHERE id_user = ?", (id_user,)).fetchone()
    if port_info is None:
        raise ValueError("Port reservation not found for the connection.")
    db.execute("INSERT INTO assigned_port (id_user, port) VALUES (?,?)", (id_user, port_info["requested_port"]))
    db.commit()
    return port_info["requested_port"]


def get_available_ports():
    valid_ports = current_app.config["VALID_PORTS"]
    db = get_db()
    dat = db.execute("SELECT port FROM assigned_port").fetchall()
    busy_ports = set([d["port"] for d in dat])
    dat = db.execute("SELECT requested_port FROM port_reservation").fetchall()
    busy_ports = busy_ports.union(set([d["requested_port"] for d in dat]))
    return list(valid_ports.difference(busy_ports))


def request_available_port(db, id_user):
    available_ports = get_available_ports()
    random.shuffle(available_ports)
    for idx_request in range(min(current_app.config["MAX_RESERVATION_ATTEMPTS"], len(available_ports))):
        if request_port(db, id_user, available_ports[idx_request]):
            # Successfully reserved
            break
    else:
        return False
    return True


def request_port(db, id_user, port):
    try:
        db.execute("INSERT INTO port_reservation (id_user, requested_port) VALUES (?,?)", (id_user, port))
        db.commit()
        return True
    except IntegrityError as e:
        return False
