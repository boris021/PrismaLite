from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["ui"])

BASE_DIR = Path(__file__).resolve().parents[1]  # app/
UI_DIR = BASE_DIR / "ui" / "incidents"


@router.get("/ui/incidents", response_class=FileResponse)
def incidents_page():
    """
    Отдаёт HTML страницу интерфейса инцидентов.
    Статика (CSS/JS) лежит в /ui/static/incidents/...
    """
    return FileResponse(UI_DIR / "index.html")
