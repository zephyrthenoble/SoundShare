from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from pydantic import BaseModel

from database.database import get_db
from database.models import DynamicCriteria, UnifiedPlaylist, unified_playlist_criteria

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Pydantic models for request/response
class DynamicCriteriaCreate(BaseModel):
    name: str
    include_criteria: Dict[str, Any] = {}
    exclude_criteria: Dict[str, Any] = {}

class DynamicCriteriaUpdate(BaseModel):
    name: Optional[str] = None
    include_criteria: Optional[Dict[str, Any]] = None
    exclude_criteria: Optional[Dict[str, Any]] = None

# Template route
@router.get("/")
async def criteria_page(request: Request):
    """Render the criteria management page."""
    return templates.TemplateResponse("criteria.html", {"request": request})

# API endpoints
@router.get("/api")
async def get_all_criteria(db: Session = Depends(get_db)):
    """Get all dynamic criteria."""
    criteria = db.query(DynamicCriteria).all()
    return criteria

@router.get("/api/{criteria_id}")
async def get_criteria(criteria_id: int, db: Session = Depends(get_db)):
    """Get a specific criteria by ID."""
    criteria = db.query(DynamicCriteria).filter(DynamicCriteria.id == criteria_id).first()
    if not criteria:
        raise HTTPException(status_code=404, detail="Criteria not found")
    return criteria

@router.post("/api")
async def create_criteria(criteria_data: DynamicCriteriaCreate, db: Session = Depends(get_db)):
    """Create a new dynamic criteria."""
    # Check if name already exists
    existing = db.query(DynamicCriteria).filter(DynamicCriteria.name == criteria_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Criteria name already exists")
    
    criteria = DynamicCriteria(
        name=criteria_data.name,
        include_criteria=criteria_data.include_criteria,
        exclude_criteria=criteria_data.exclude_criteria
    )
    
    db.add(criteria)
    db.commit()
    db.refresh(criteria)
    return criteria

@router.put("/api/{criteria_id}")
async def update_criteria(criteria_id: int, criteria_data: DynamicCriteriaUpdate, db: Session = Depends(get_db)):
    """Update an existing criteria."""
    criteria = db.query(DynamicCriteria).filter(DynamicCriteria.id == criteria_id).first()
    if not criteria:
        raise HTTPException(status_code=404, detail="Criteria not found")
    
    # Check if new name already exists (if name is being changed)
    if criteria_data.name and criteria_data.name != criteria.name:
        existing = db.query(DynamicCriteria).filter(DynamicCriteria.name == criteria_data.name).first()
        if existing:
            raise HTTPException(status_code=400, detail="Criteria name already exists")
        criteria.name = criteria_data.name
    
    if criteria_data.include_criteria is not None:
        criteria.include_criteria = criteria_data.include_criteria
    if criteria_data.exclude_criteria is not None:
        criteria.exclude_criteria = criteria_data.exclude_criteria
    
    db.commit()
    db.refresh(criteria)
    return criteria

@router.delete("/api/{criteria_id}")
async def delete_criteria(criteria_id: int, db: Session = Depends(get_db)):
    """Delete a criteria."""
    criteria = db.query(DynamicCriteria).filter(DynamicCriteria.id == criteria_id).first()
    if not criteria:
        raise HTTPException(status_code=404, detail="Criteria not found")
    
    db.delete(criteria)
    db.commit()
    return {"message": "Criteria deleted successfully"}

@router.get("/api/{criteria_id}/playlists")
async def get_criteria_playlists(criteria_id: int, db: Session = Depends(get_db)):
    """Get all playlists that use this criteria."""
    criteria = db.query(DynamicCriteria).filter(DynamicCriteria.id == criteria_id).first()
    if not criteria:
        raise HTTPException(status_code=404, detail="Criteria not found")
    
    # Query playlists that use this criteria
    playlists = db.query(UnifiedPlaylist).join(
        unified_playlist_criteria,
        UnifiedPlaylist.id == unified_playlist_criteria.c.unified_playlist_id
    ).filter(
        unified_playlist_criteria.c.criteria_id == criteria_id
    ).all()
    
    return playlists
