from fastapi import APIRouter, HTTPException

from app.database.mongodb import teams_async_collection
from app.models.schemas import LeaderDetailsResponse

router = APIRouter(tags=["teams"])


@router.get("/api/team/{team_id}/leader-details", response_model=LeaderDetailsResponse)
async def team_leader_details(team_id: str):
    team = await teams_async_collection.find_one({"teamId": team_id}, {"_id": 0})
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    return LeaderDetailsResponse(
        teamId=team["teamId"],
        leaderEmail=team.get("leaderEmail", ""),
        collegeName=team["collegeName"],
        branch=team["branch"],
        projectSelected=team.get("projectSelected") or team.get("taskSelected") or "",
        taskSelected=team.get("taskSelected") or team.get("projectSelected"),
        assignedChallenge=None,
    )