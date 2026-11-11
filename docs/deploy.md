# Put it online for free

This puts the project on three free services, so anyone can open it from a link.

| Piece | Service | What it does |
|---|---|---|
| Database | [Neon](https://neon.com) | Hosts PostgreSQL. It sleeps when idle and wakes in about a second |
| API | [Render](https://render.com) | Builds the `Dockerfile` and runs the API. Redeploys on every merge to `main` |
| Website | [Cloudflare Pages](https://pages.cloudflare.com) | Builds `frontend/` and serves it. Redeploys on every merge to `main` |
| Keep-awake | [UptimeRobot](https://uptimerobot.com) | Calls `/health` every 5 minutes so the API never sleeps |

Free plans change. Check each service's current limits before you rely on it.

You need accounts on all four, the repo on GitHub, and the data loaded locally (see the README).

## 1. Database on Neon

1. Create a Neon project with Postgres 16 or later.
2. Copy its connection string. It starts with `postgresql://` and ends with `sslmode=require`.
3. Copy your local data into it. Start the local database with `docker compose up -d db`, then run this with your Neon string in place of the example:

   ```bash
   docker compose exec -e NEON_URL="postgresql://user:password@host/dbname?sslmode=require" db sh -c 'pg_dump -U "$POSTGRES_USER" --no-owner --no-acl "$POSTGRES_DB" | psql "$NEON_URL"'
   ```

   The command works in PowerShell and in bash. It copies the tables and every row. Run it once, into an empty database.

**Check:** Neon's SQL editor shows rows for `SELECT count(*) FROM races;`.

Neon's free plan holds about 0.5 GB. Seasons 2000 to 2026 take 38 MB.

## 2. API on Render

1. In Render, choose **New**, then **Blueprint**, and pick this repo. Render reads `render.yaml`.
2. It asks for three values:
   - `DATABASE_URL`: the Neon connection string.
   - `ANTHROPIC_API_KEY`: your key from [console.anthropic.com](https://console.anthropic.com). Leave it empty to run without the engineer.
   - `CORS_ORIGINS`: the website's address. You get it in step 3, so enter `http://localhost:5173` for now.
3. Wait for the first deploy. Render shows the API's address, like `https://f1-race-analyst-api.onrender.com`.

**Check:** `/health` on that address returns `{"status":"ok"}`, and `/races` returns races.

## 3. Website on Cloudflare Pages

1. In the Cloudflare dashboard, create a Pages project and connect this repo.
2. Use these build settings:

   | Setting | Value |
   |---|---|
   | Root directory | `frontend` |
   | Build command | `npm run build` |
   | Build output directory | `dist` |

3. Add two environment variables:
   - `VITE_API_URL`: the Render address from step 2, with no slash at the end.
   - `NODE_VERSION`: `24`.
4. Deploy. Cloudflare shows the site's address, like `https://f1-race-analyst.pages.dev`.
5. Back in Render, set `CORS_ORIGINS` to that address, with no slash at the end. Render restarts the API.

**Check:** the site opens on your phone, a race page shows its charts, and the engineer answers a question.

## 4. Keep the API awake

Render's free plan stops an API that has had no visitors for 15 minutes, and the next visitor waits up to a minute.

In UptimeRobot, add an HTTP monitor for `https://<your-api>.onrender.com/health` every 5 minutes.

`/health` does not query the database, so the pings keep the API awake and let Neon sleep.

## 5. Cap the spending

- Set a monthly spend limit in the Anthropic console. This is the hard stop.
- The API's own limits still apply: 5 questions per minute per visitor and $1 per day. The daily count is kept in memory, so it starts again whenever Render restarts the API.

## Updating and shutting down

- **Update:** merge a pull request into `main`. Render and Cloudflare both redeploy.
- **New race data:** load it locally with `scripts.load_data`, then run that loader against Neon by setting `DATABASE_URL` to the Neon string for one command. The step 1 copy is only for an empty database.
- **Shut down:** delete the Render service, the Pages project, the Neon project and the UptimeRobot monitor. Nothing bills while they exist, but the Anthropic key should be removed from Render if you stop using it.

## Known limits of this setup

- The rate limit trusts the visitor address that Render's proxy passes on (`FORWARDED_ALLOW_IPS=*`). A visitor who forges that header could dodge the per-minute limit. The daily cap and the Anthropic spend limit still hold.
- If the uptime pings stop, the first visitor after a quiet spell waits while Render starts the API. The site says "Warming up" during that wait.
