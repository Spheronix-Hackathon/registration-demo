import re

from fastapi import APIRouter, Query

from app.database.mongodb import colleges_async_collection

router = APIRouter(prefix="/api/colleges", tags=["colleges"])


@router.get("")
async def get_colleges(
    q: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=1000, ge=1, le=5000),
    include_other: bool = Query(default=True),
):
    filter_query = {"is_other": False}
    if q:
        filter_query["name_lc"] = {"$regex": re.escape(q.strip().lower())}

    projection = {"_id": 0, "name": 1, "code": 1, "is_other": 1, "sort_order": 1}
    colleges = await colleges_async_collection.find(filter_query, projection).sort("sort_order", 1).to_list(length=limit)

    if include_other:
        other_college = await colleges_async_collection.find_one({"is_other": True}, projection)
        if other_college:
            colleges.append(other_college)

    return {"colleges": colleges, "total": len(colleges)}
