#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python packages
pip install --upgrade pip
pip install -r requirements.txt

# Run the data ingestion script
python scripts/ingest.py
