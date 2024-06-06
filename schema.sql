PRAGMA foreign_keys = ON;

CREATE TABLE port_reservation (
    id_user VARCHAR(36) PRIMARY KEY NOT NULL,
    requested_port VARCHAR(5) UNIQUE NOT NULL,  -- port that the image should use
    request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE assigned_port (
    id_user VARCHAR(36) PRIMARY KEY NOT NULL,
    port VARCHAR(5) UNIQUE NOT NULL,  -- port that the docker image is running on
    assigned_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE running_container (
    id_user VARCHAR(36) PRIMARY KEY,
    port VARCHAR(5) UNIQUE NOT NULL,
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- When a container is started and registered, remove
CREATE TRIGGER container_start
    AFTER INSERT
    ON running_container
    FOR EACH ROW
BEGIN
    DELETE FROM assigned_port WHERE assigned_port.port = NEW.port;
END;

-- When a port is assigned, remove it from reservation
CREATE TRIGGER remove_reservation
    AFTER INSERT ON assigned_port
    FOR EACH ROW
    BEGIN
        DELETE FROM port_reservation WHERE port_reservation.requested_port = NEW.port;
    END;

-- Checks whether the port is otherwise reserved.
CREATE TRIGGER check_reservation
    BEFORE INSERT ON port_reservation
    BEGIN
        SELECT CASE
            WHEN (((SELECT port FROM assigned_port WHERE assigned_port.port = NEW.requested_port) IS NOT NULL) OR
                  (SELECT port FROM running_container WHERE running_container.port = NEW.requested_port) IS NOT NULL)
            THEN RAISE(ABORT, "The requested port is already assigned.")
        END;
    END;
