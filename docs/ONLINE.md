# Online API (development only)

The online API is not ready for a real company. It refuses to start unless `VCA_ENV` is `development`, and it listens on 127.0.0.1 only. There is no sign-in. The development member is chosen with `VCA_DEV_MEMBER`, which must match a member's OS user name on that company.

| Variable | Example |
|---|---|
| `VCA_ENV` | `development` |
| `VCA_DATABASE_URL` | `postgresql+psycopg://vca_app:vca_dev_only@127.0.0.1:5432/vca` |
| `VCA_DEV_MEMBER` | `dev` |
| `VCA_PORT` | `8000` |

The host name's first label is the company subdomain, for example `alpha.vantagecorepro.com`. A local Postgres for this check is `docker-compose.dev.yml`. The database role in that file is for this computer only.

Uploading a desktop company file is not available. The import routes answer 501 with "Awaiting security review."

The web screens live in `web/ui`. `npm ci` and `npm run build` from that folder produce the static files. A browser smoke check is in `web/ui/e2e` and is not run by default.
