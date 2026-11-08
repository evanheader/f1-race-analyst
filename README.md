# f1-race-analyst

[![CI](https://github.com/evanheader/f1-race-analyst/actions/workflows/ci.yml/badge.svg)](https://github.com/evanheader/f1-race-analyst/actions/workflows/ci.yml)

A REST API for looking up Formula 1 race results, lap times, tire stints and pit stops, built with FastAPI and PostgreSQL.

This is an unofficial fan project, not affiliated with Formula 1. Race data comes from [Jolpica](https://github.com/jolpica/jolpica-f1) and [OpenF1](https://openf1.org/).

## How to run

You need [Docker Desktop](https://www.docker.com/products/docker-desktop/) running.

1. Copy `.env.example` to a new file named `.env`. The values work as they are for running on your own computer.

   ```bash
   cp .env.example .env
   ```

2. Start the database and the API.

   ```bash
   docker compose up --build -d
   ```

3. Create the tables. You only need to do this once.

   ```bash
   docker compose exec api python -m scripts.create_tables
   ```

4. Load some data. Pick one:

   **Quick demo (a few seconds, no internet needed).** Loads one race, the 2025 British Grand Prix: results, every lap with its tire, and every pit stop. It was a mixed-conditions race that Norris won and Hülkenberg took third in from 19th on the grid.

   ```bash
   docker compose exec api python -m scripts.load_sample
   ```

   **Full 2025 season.** This downloads from the data sources and takes several minutes. It is safe to run again: rows are updated, not duplicated.

   ```bash
   docker compose exec api python -m scripts.load_data
   ```

   If it stops with a `401` or `429`, a live F1 session or a rate limit is blocking the data source. Run the same command again later. To load other seasons, pass them: `python -m scripts.load_data 2023 2024`.

5. Open <http://localhost:8000/docs> to try the API, or <http://localhost:8000/races> to see the races. With the quick demo, try <http://localhost:8000/races/1/results> and <http://localhost:8000/races/1/pit-stops>.

To stop everything, run `docker compose down`. Your data is kept for next time.

## Run the tests

The tests use a separate `f1_test` database, so they never touch your real data, and they never call the internet.

1. Start the database, and create `f1_test` once.

   ```bash
   docker compose up -d db
   docker compose exec db createdb -U f1 f1_test
   ```

2. Run the checks that CI runs.

   ```bash
   uv run ruff check .
   uv run ruff format --check .
   uv run pytest --cov=app --cov=scripts
   ```

## More documentation

- [DESIGN.md](DESIGN.md): why the project is built this way
- [docs/schema.md](docs/schema.md): every table and column
- [docs/api-reference.md](docs/api-reference.md): notes on the two data sources
