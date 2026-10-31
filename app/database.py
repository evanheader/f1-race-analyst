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
