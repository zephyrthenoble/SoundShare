from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional
from pydantic import BaseModel

from database.database import get_db
from database.models import Tag, TagGroup

router = APIRouter()

class TagGroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = "#007bff"

class TagCreate(BaseModel):
    name: str
    description: Optional[str] = None
    group_id: Optional[int] = None

class TagGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None

class TagUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    group_id: Optional[int] = None

# Tag Groups
@router.get("/groups")
async def get_tag_groups(db: Session = Depends(get_db)):
    """Get all tag groups with their tags."""
    groups = db.query(TagGroup).options(selectinload(TagGroup.tags)).all()
    return groups

@router.post("/groups")
async def create_tag_group(group: TagGroupCreate, db: Session = Depends(get_db)):
    """Create a new tag group."""
    db_group = TagGroup(**group.dict())
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

@router.put("/groups/{group_id}")
async def update_tag_group(
    group_id: int, 
    group_update: TagGroupUpdate, 
    db: Session = Depends(get_db)
):
    """Update a tag group."""
    group = db.query(TagGroup).filter(TagGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Tag group not found")
    
    update_data = group_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(group, field, value)
    
    db.commit()
    db.refresh(group)
    return group

@router.delete("/groups/{group_id}")
async def delete_tag_group(group_id: int, db: Session = Depends(get_db)):
    """Delete a tag group and all its tags."""
    group = db.query(TagGroup).filter(TagGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Tag group not found")
    
    db.delete(group)
    db.commit()
    return {"message": "Tag group deleted"}

# Tags
@router.get("/")
async def get_tags(group_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Get all tags, optionally filtered by group."""
    query = db.query(Tag)
    if group_id:
        query = query.filter(Tag.group_id == group_id)
    tags = query.all()
    return tags

@router.post("/")
async def create_tag(tag: TagCreate, db: Session = Depends(get_db)):
    """Create a new tag."""
    db_tag = Tag(**tag.dict())
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return db_tag

@router.put("/{tag_id}")
async def update_tag(tag_id: int, tag_update: TagUpdate, db: Session = Depends(get_db)):
    """Update a tag."""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    update_data = tag_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tag, field, value)
    
    db.commit()
    db.refresh(tag)
    return tag

@router.delete("/{tag_id}")
async def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    """Delete a tag."""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    db.delete(tag)
    db.commit()
    return {"message": "Tag deleted"}
