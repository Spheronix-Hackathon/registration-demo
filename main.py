import uvicorn

from app.main import app
from config.settings import get_settings

settings = get_settings()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.server_host, port=settings.server_port, reload=False)
