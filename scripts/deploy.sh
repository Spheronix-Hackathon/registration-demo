#!/bin/bash

# Deployment Script for Spheronix Hackathon API
# Usage: ./scripts/deploy.sh

set -e

APP_DIR="/opt/hackathon/app"
SERVICE_NAME="hackathon.service"

echo "Starting deployment..."

cd $APP_DIR

# Pull latest changes from git (assuming ssh keys are set up)
echo "Pulling latest changes..."
git pull origin main

# Update virtual environment
echo "Updating dependencies..."
source venv/bin/activate
pip install -r requirements.txt

# Restart systemd service
echo "Restarting service..."
sudo systemctl restart $SERVICE_NAME

# Check status
echo "Checking service status..."
sudo systemctl status $SERVICE_NAME --no-pager

echo "Deployment complete!"
