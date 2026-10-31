import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

from models import Base


def main() -> None:
    load_dotenv()
    engine = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.create_all(engine)


if __name__ == "__main__":
    main()
