from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional
from pydantic import BaseModel

from database.database import get_db
from database.models import TagGroup, Tag

router = APIRouter()

class TagGroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    color: str = "#007bff"
    tags: List[dict] = []

    class Config:
        from_attributes = True

class TagGroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = "#007bff"

class TagGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None

@router.get("/", response_model=List[TagGroupResponse])
async def get_groups(db: Session = Depends(get_db)):
    """Get all tag groups with their tags."""
    groups = db.query(TagGroup).options(selectinload(TagGroup.tags)).all()
    
    # Format the response to include tag information
    response = []
    for group in groups:
        group_data = {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "color": group.color,
            "tags": [{"id": tag.id, "name": tag.name} for tag in group.tags]
        }
        response.append(group_data)
    
    return response

@router.get("/{group_id}")
async def get_group(group_id: int, db: Session = Depends(get_db)):
    """Get a specific tag group with its tags."""
    group = db.query(TagGroup).options(selectinload(TagGroup.tags)).filter(TagGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Tag group not found")
    
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "color": group.color,
        "tags": [{"id": tag.id, "name": tag.name} for tag in group.tags]
    }

@router.post("/", response_model=TagGroupResponse)
async def create_group(group: TagGroupCreate, db: Session = Depends(get_db)):
    """Create a new tag group."""
    # Check if group with this name already exists
    existing_group = db.query(TagGroup).filter(TagGroup.name == group.name).first()
    if existing_group:
        raise HTTPException(status_code=400, detail="Tag group with this name already exists")
    
    db_group = TagGroup(**group.model_dump())
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    
    return {
        "id": db_group.id,
        "name": db_group.name,
        "description": db_group.description,
        "color": db_group.color,
        "tags": []
    }

@router.put("/{group_id}")
async def update_group(
    group_id: int, 
    group_update: TagGroupUpdate, 
    db: Session = Depends(get_db)
):
    """Update a tag group."""
    group = db.query(TagGroup).filter(TagGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Tag group not found")
    
    # Check for name conflicts if name is being updated
    if group_update.name and group_update.name != group.name:
        existing_group = db.query(TagGroup).filter(TagGroup.name == group_update.name).first()
        if existing_group:
            raise HTTPException(status_code=400, detail="Tag group with this name already exists")
    
    update_data = group_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(group, field, value)
    
    db.commit()
    db.refresh(group)
    
    # Load tags for response
    updated_group = db.query(TagGroup).options(selectinload(TagGroup.tags)).filter(TagGroup.id == group_id).first()
    if not updated_group:
        raise HTTPException(status_code=404, detail="Tag group not found after update")
    
    return {
        "id": updated_group.id,
        "name": updated_group.name,
        "description": updated_group.description,
        "color": updated_group.color,
        "tags": [{"id": tag.id, "name": tag.name} for tag in updated_group.tags]
    }

@router.delete("/{group_id}")
async def delete_group(group_id: int, db: Session = Depends(get_db)):
    """Delete a tag group. Tags in this group will become ungrouped."""
    group = db.query(TagGroup).filter(TagGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Tag group not found")
    
    # Set group_id to None for all tags in this group (don't delete the tags)
    db.query(Tag).filter(Tag.group_id == group_id).update({"group_id": None})
    
    db.delete(group)
    db.commit()
    return {"message": f"Tag group '{group.name}' deleted. Tags are now ungrouped."}
