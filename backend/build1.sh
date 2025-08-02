#!/bin/bash

# Exit on any error
set -e

# Install Python packages
pip install -r requirements.txt

# Run the data ingestion script
# This will build the vector_store on the server
python ingest.py