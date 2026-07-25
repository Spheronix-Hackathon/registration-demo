from fastapi import APIRouter, Response
from fastapi.responses import StreamingResponse
from app.services.export_service import generate_problem_statements_docx
import logging

router = APIRouter(prefix="/api/exports", tags=["exports"])
logger = logging.getLogger(__name__)

@router.get("/problems/word")
async def export_problems_to_word():
    try:
        buffer = generate_problem_statements_docx()
        filename = "Spheronix_Hackathon_2026_Problem_Statements.docx"
        
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Failed to export problem statements to Word: {str(e)}")
        return Response(content="Internal Server Error", status_code=500)
