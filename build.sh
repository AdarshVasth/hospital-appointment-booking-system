#!/usr/bin/env bash
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py seed_demo

# One-time superuser provisioning on Render's free tier.
# Set both environment variables privately in Render; remove them after deployment.
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  python manage.py provision_render_admin
fi
