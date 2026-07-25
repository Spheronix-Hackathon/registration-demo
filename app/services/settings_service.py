from app.database.mongodb import async_db

async def get_registration_fee() -> float:
    settings_collection = async_db["settings"]
    settings_doc = await settings_collection.find_one()
    if settings_doc and "registrationAmount" in settings_doc:
        return float(settings_doc["registrationAmount"])
    return 1800.0
