from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import os
import sys
import io
import contextlib
import logging

# Add parent directory to sys.path to import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.main import cmd_validate, cmd_dry_run, cmd_send
from src.database import db
from src.config import settings
from src.logger import result_logger

app = FastAPI(title="WhatsApp Recruitment Dashboard")

# Models
class CampaignRequest(BaseModel):
    category: Optional[str] = None
    experience: Optional[str] = "all"
    campaign_id: Optional[str] = None
    job_title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    apply_link: Optional[str] = None
    limit: Optional[int] = None
    confirm: bool = False

# Global state to capture logs for the UI
class LogCapture:
    def __init__(self):
        self.output = io.StringIO()
    
    def get_output(self):
        val = self.output.getvalue()
        # self.output.truncate(0)
        # self.output.seek(0)
        return val

log_capture = LogCapture()

@app.get("/api/folders")
def get_folders():
    folders = db.get_all_folders()
    return [{"id": f["id"], "name": f["name"], "list_count": f.get("list_count")} for f in folders]

@app.get("/api/folder-levels")
def get_folder_levels(folder: str):
    mapping = db.get_lists_by_folder_name(folder)
    return list(mapping.keys())

@app.get("/api/validate")
def validate():
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        success = cmd_validate()
    return {"success": success, "logs": f.getvalue()}

@app.post("/api/dry-run")
def dry_run(req: CampaignRequest):
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        cmd_dry_run(
            limit=req.limit,
            experience=req.experience,
            campaign_id=req.campaign_id,
            category=req.category
        )
    return {"logs": f.getvalue()}

@app.post("/api/send")
def send(req: CampaignRequest):
    if not req.confirm:
        return {"error": "Confirmation required for live send", "logs": ""}
    
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        cmd_send(
            limit=req.limit,
            confirm=req.confirm,
            experience=req.experience,
            campaign_id=req.campaign_id,
            category=req.category,
            job_title=req.job_title,
            company=req.company,
            location=req.location,
            apply_link=req.apply_link
        )
    return {"logs": f.getvalue()}

@app.get("/api/summary")
def summary():
    # This might be tricky if it only prints. Let's assume we want the last 24h stats.
    import sqlite3
    conn = sqlite3.connect("send_history.db")
    cursor = conn.cursor()
    cursor.execute("SELECT status, count(*) FROM send_history WHERE sent_at >= datetime('now', '-1 day') GROUP BY status")
    stats = dict(cursor.fetchall())
    conn.close()
    return {
        "success": stats.get("success", 0),
        "failed": stats.get("failed", 0),
        "total": sum(stats.values()),
        "limit": settings.DAILY_LIMIT
    }

# Serve static files
os.makedirs("web_ui/static", exist_ok=True)
app.mount("/", StaticFiles(directory="web_ui/static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
