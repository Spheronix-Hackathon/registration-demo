from fastapi import APIRouter
from app.database.mongodb import global_data_async_collection, branches_async_collection

router = APIRouter(prefix="/api", tags=["tasks"])

@router.get("/task-categories")
async def get_task_categories():
    projection = {"_id": 0, "name": 1}
    categories = await global_data_async_collection.find({}, projection).to_list(length=100)
    return [c["name"] for c in categories]

@router.get("/branches")
async def get_branches():
    projection = {"_id": 0, "name": 1}
    branches = await branches_async_collection.find({}, projection).sort("name", 1).to_list(length=100)
    return [b["name"] for b in branches]
