from fastapi import APIRouter
from app.database.mongodb import async_db

router = APIRouter(prefix="/api/public-settings", tags=["Settings"])

@router.get("/")
async def get_public_settings():
    settings_collection = async_db["settings"]
    settings = await settings_collection.find_one()
    
    amount = 1800
    is_open = True
    
    if settings:
        if "registrationAmount" in settings:
            amount = settings["registrationAmount"]
        if "registrationOpen" in settings:
            is_open = settings["registrationOpen"]
            
    return {
        "registrationAmount": amount,
        "registrationOpen": is_open
    }
