import multiprocessing
import os

# Server socket
bind = "127.0.0.1:8000"
backlog = 2048

# Worker processes
# Fix P-04: For async FastAPI, 2-4 workers is typically optimal.
# (cpu_count * 2 + 1) creates too many workers on high-CPU servers, wasting RAM
# and exhausting MongoDB Atlas connection limits. Cap at 4.
workers = min(4, multiprocessing.cpu_count() * 2 + 1)
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
timeout = 120
keepalive = 2

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = "hackathon_api"

# Environment variables
# These are usually handled by the systemd service file or .env
# env = {"APP_ENV": "production"}
