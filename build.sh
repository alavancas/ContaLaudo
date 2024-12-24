#!/usr/bin/env bash
# exit on error
set -o errexit

# Install system dependencies for psycopg2
apt-get update
apt-get install -y python3-dev libpq-dev gcc

# Install Python dependencies
pip install -r requirements.txt
