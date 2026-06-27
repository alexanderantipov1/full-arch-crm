# Environment files

Maintain a separate `.env` per deployment target. Never commit real values.

| File          | Purpose                            |
|---------------|------------------------------------|
| `.env`        | Active config (root of `platform/`) |
| `.env.dev`    | Local Mac dev — copy from project root `.env.example` |
| `.env.prod`   | Office server — keep on server only, mode `0600`, owned by deploy user |

Use the project root `.env.example` as the template. Override only what differs:

* `APP_ENV=production`
* Strong `SECRET_KEY` (≥ 32 random bytes)
* Strong `POSTGRES_PASSWORD`
* `GCS_BUCKET` set to the BAA-covered bucket
* `GOOGLE_APPLICATION_CREDENTIALS` mounted into the worker container at `/secrets/gcp-sa.json`
