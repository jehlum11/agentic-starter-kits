from urllib.parse import quote_plus
from os import getenv

from dotenv import load_dotenv


def get_env_var(env_key: str) -> str | None:
    """
    Get an environment variable. If not present, load .env file and try again.
    If failed again rise EnvironmentError.
    :param env_key:
    :return:
    """

    value = getenv(env_key)
    if value:
        return value.strip()
    else:
        load_dotenv()
        value = getenv(env_key)
        if not value:
            EnvironmentError(f"Environment variable `{env_key}` is not set")

    return value


def get_database_uri() -> str:
    """
    Construct PostgresSQL database URI from environment variables.

    Expected env vars:
    - POSTGRES_HOST
    - POSTGRES_PORT
    - POSTGRES_DB
    - POSTGRES_USER
    - POSTGRES_PASSWORD
    """
    host = get_env_var("POSTGRES_HOST")
    user = get_env_var("POSTGRES_USER")
    password = get_env_var("POSTGRES_PASSWORD")
    database = get_env_var("POSTGRES_DB")
    port = get_env_var("POSTGRES_PORT")

    safe_host = quote_plus(host)
    safe_user = quote_plus(user)
    safe_password = quote_plus(password)

    return f"postgresql://{safe_user}:{safe_password}@{safe_host}:{port}/{database}"
