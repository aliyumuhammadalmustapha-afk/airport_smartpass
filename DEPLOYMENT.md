# Render deployment and handoff

## Deploy

1. Push this folder to a private GitHub repository and connect that repository to Render as a Blueprint using `render.yaml`.
2. Render creates a web service and Postgres database. The free Postgres plan expires after 30 days; choose a paid database before this becomes the owner's live system.
3. The blueprint turns off Django debug mode, generates a secret key, collects static files, and applies migrations during each build.
4. Create the owner administrator on the deployed service using the Render Shell: `python manage.py createsuperuser`. Use the same email address as the current admin if the owner should keep that login identity, and set a new password. The clean production database does not carry over the local password or other test records.
5. If the owner needs gate staff access, create a separate user and grant `is_staff`; do not share the superuser login with gate staff.

## Files and data

Postgres preserves accounts, bookings, and scan logs. Generated boarding pass QR images can be recreated from their database records when a passenger opens their pass. The default free web service filesystem is temporary, so other media files must not be treated as durable. To preserve media on Render, use external object storage or a paid service with a persistent disk mounted at `/var/data`, then set `MEDIA_ROOT=/var/data/media`.

## Verify before handoff

- Register a passenger, log out, then log back in with the same email and password.
- Restart/redeploy the web service and confirm that passenger login, bookings, and admin access remain.
- Check booking, check-in, QR display, QR scan, PDF download, and static CSS/JavaScript.
- Confirm the intended owner superuser and any gate staff accounts exist in the production database.
- Review the deployment logs and confirm migrations completed successfully.

## ZIP contents

Include application source, migrations, templates, static source assets, `requirements.txt`, `build.sh`, `render.yaml`, `.env.example`, and this guide. Exclude `db.sqlite3`, virtual environments, local `.env` files, `media/`, generated `staticfiles/`, Python caches, backups, and local screenshots unless the owner requests them. The `.gitignore` covers the main generated and sensitive local files.
