import os
from collections.abc import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

load_dotenv()
engine = create_engine(os.environ["DATABASE_URL"])


def get_db() -> Iterator[Session]:
    """One database session per request, closed when the request ends."""
    with Session(engine) as session:
        yield session


def get_read_only_db() -> Iterator[Session]:
    """Like get_db, but Postgres itself rejects any write on this session."""
    with Session(engine.execution_options(postgresql_readonly=True)) as session:
        yield session
