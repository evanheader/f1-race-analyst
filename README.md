# f1-race-analyst

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

4. Load the 2023 and 2024 seasons. This takes about 10 minutes. It is safe to run again: rows are updated, not duplicated.

   ```bash
   docker compose exec api python -m scripts.load_data
   ```

   If it stops with a `401` or `429`, a live F1 session or a rate limit is blocking the data source. Run the same command again later.

5. Open <http://localhost:8000/docs> to try the API, or <http://localhost:8000/races> to see the races.

To stop everything, run `docker compose down`. Your data is kept for next time.

## More documentation

- [DESIGN.md](DESIGN.md): why the project is built this way
- [docs/schema.md](docs/schema.md): every table and column
- [docs/api-reference.md](docs/api-reference.md): notes on the two data sources
