import json
from os.path import join


def get_config(*args) -> dict:
    config = dict()

    for env_file in args:
        env = parse_env(env_file)
        config |= env
    config["VALID_PORTS"] = set([str(i) for i in range(config["START_PORT"], config["START_PORT"] + config["MAX_INSTANCES"])])
    config["DATABASE_PATH"] = join(config["INSTANCE_PATH"], config["DATABASE_FILENAME"])
    config["SQL_SCHEMA_PATH"] = join(config["INSTANCE_PATH"], config["SQL_SCHEMA_FILENAME"])
    return config


def parse_env(env_file: str = '.env') -> dict:
    """
    Parses the environment file and returns the result as a dict.
    Parameters
    ----------
    env_file : str
        Path to the environment

    Returns
    -------
    dict
        Dictionary keyed with the environment variable name.
    """
    f = open(env_file)
    env_dict = dict()
    line = f.readline()
    line_count = 0  # on the off chance that the problematic line contains the secret key, don't print contents
    while len(line) > 0:
        line_count += 1
        idx_equal = line.index('=')
        if idx_equal == -1:
            raise ValueError(f"Environment file not correctly configured; see line {line_count} in .env file.")
        key = line[:idx_equal]
        env_dict[key] = json.loads(line[idx_equal+1:])
        line = f.readline()
    f.close()
    return env_dict
