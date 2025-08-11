from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional
from pydantic import BaseModel
import os

from database.database import get_db
from database.models import DynamicPlaylist, Tag, TagGroup, Song

router = APIRouter()

class DynamicPlaylistCreate(BaseModel):
    name: str
    description: Optional[str] = None
    include_tag_ids: List[int] = []
    exclude_tag_ids: List[int] = []
    include_group_ids: List[int] = []
    exclude_group_ids: List[int] = []
    # Audio feature filters
    energy_min: Optional[float] = None
    energy_max: Optional[float] = None
    valence_min: Optional[float] = None
    valence_max: Optional[float] = None
    danceability_min: Optional[float] = None
    danceability_max: Optional[float] = None

class DynamicPlaylistUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    include_tag_ids: Optional[List[int]] = None
    exclude_tag_ids: Optional[List[int]] = None
    include_group_ids: Optional[List[int]] = None
    exclude_group_ids: Optional[List[int]] = None
    # Audio feature filters
    energy_min: Optional[float] = None
    energy_max: Optional[float] = None
    valence_min: Optional[float] = None
    valence_max: Optional[float] = None
    danceability_min: Optional[float] = None
    danceability_max: Optional[float] = None

@router.get("/")
async def get_dynamic_playlists(db: Session = Depends(get_db)):
    """Get all dynamic playlists."""
    playlists = db.query(DynamicPlaylist).options(
        selectinload(DynamicPlaylist.include_tags),
        selectinload(DynamicPlaylist.exclude_tags),
        selectinload(DynamicPlaylist.include_groups),
        selectinload(DynamicPlaylist.exclude_groups)
    ).all()
    return playlists

@router.get("/{playlist_id}")
async def get_dynamic_playlist(playlist_id: int, db: Session = Depends(get_db)):
    """Get a specific dynamic playlist."""
    playlist = db.query(DynamicPlaylist).options(
        selectinload(DynamicPlaylist.include_tags),
        selectinload(DynamicPlaylist.exclude_tags),
        selectinload(DynamicPlaylist.include_groups),
        selectinload(DynamicPlaylist.exclude_groups)
    ).filter(DynamicPlaylist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Dynamic playlist not found")
    return playlist

@router.get("/{playlist_id}/songs")
async def get_dynamic_playlist_songs(playlist_id: int, db: Session = Depends(get_db)):
    """Generate and return songs that match the dynamic playlist criteria."""
    playlist = db.query(DynamicPlaylist).options(
        selectinload(DynamicPlaylist.include_tags),
        selectinload(DynamicPlaylist.exclude_tags),
        selectinload(DynamicPlaylist.include_groups).selectinload(TagGroup.tags),
        selectinload(DynamicPlaylist.exclude_groups).selectinload(TagGroup.tags)
    ).filter(DynamicPlaylist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Dynamic playlist not found")
    
    # Start with all songs
    query = db.query(Song)
    
    # Include songs that have ANY of the include tags
    include_conditions = []
    if playlist.include_tags:
        include_tag_ids = [tag.id for tag in playlist.include_tags]
        include_conditions.append(Song.tags.any(Tag.id.in_(include_tag_ids)))
    
    # Include songs that have ANY tag from ANY of the include groups
    if playlist.include_groups:
        for group in playlist.include_groups:
            if group.tags:
                group_tag_ids = [tag.id for tag in group.tags]
                include_conditions.append(Song.tags.any(Tag.id.in_(group_tag_ids)))
    
    # Apply include conditions (song must match at least one condition)
    if include_conditions:
        from sqlalchemy import or_
        query = query.filter(or_(*include_conditions))
    
    # Exclude songs that have ANY of the exclude tags
    exclude_conditions = []
    if playlist.exclude_tags:
        exclude_tag_ids = [tag.id for tag in playlist.exclude_tags]
        exclude_conditions.extend(exclude_tag_ids)
    
    # Exclude songs that have ANY tag from ANY of the exclude groups
    if playlist.exclude_groups:
        for group in playlist.exclude_groups:
            if group.tags:
                group_tag_ids = [tag.id for tag in group.tags]
                exclude_conditions.extend(group_tag_ids)
    
    # Apply exclude conditions
    if exclude_conditions:
        query = query.filter(~Song.tags.any(Tag.id.in_(exclude_conditions)))
    
    # Apply audio feature filters
    if playlist.energy_min is not None:
        query = query.filter(Song.energy >= playlist.energy_min)
    if playlist.energy_max is not None:
        query = query.filter(Song.energy <= playlist.energy_max)
    if playlist.valence_min is not None:
        query = query.filter(Song.valence >= playlist.valence_min)
    if playlist.valence_max is not None:
        query = query.filter(Song.valence <= playlist.valence_max)
    if playlist.danceability_min is not None:
        query = query.filter(Song.danceability >= playlist.danceability_min)
    if playlist.danceability_max is not None:
        query = query.filter(Song.danceability <= playlist.danceability_max)

    songs = query.distinct().all()
    
    # Check each song's file existence and collect songs to remove
    songs_to_remove = []
    valid_songs = []
    
    for song in songs:
        if not os.path.exists(song.file_path):
            print(f"Song file not found: {song.file_path}, removing song ID {song.id}")
            songs_to_remove.append(song)
        else:
            # Check if file is zero length
            try:
                file_size = os.path.getsize(song.file_path)
                if file_size == 0:
                    print(f"Song file is zero length: {song.file_path}, removing song ID {song.id}")
                    songs_to_remove.append(song)
                else:
                    valid_songs.append(song)
            except OSError:
                # File exists but can't read it (permissions, etc.)
                print(f"Cannot access song file: {song.file_path}, removing song ID {song.id}")
                songs_to_remove.append(song)
    
    # Remove songs whose files don't exist or are zero-length
    if songs_to_remove:
        for song in songs_to_remove:
            # Clear all tag relationships (SQLAlchemy will handle the many-to-many cleanup)
            song.tags.clear()
            
            # Delete the song itself
            db.delete(song)
        
        # Commit the deletions
        db.commit()
        
        print(f"Cleaned up {len(songs_to_remove)} songs with missing/zero-length files from dynamic playlist")
    
    return valid_songs

@router.post("/")
async def create_dynamic_playlist(playlist: DynamicPlaylistCreate, db: Session = Depends(get_db)):
    """Create a new dynamic playlist."""
    db_playlist = DynamicPlaylist(
        name=playlist.name,
        description=playlist.description,
        energy_min=playlist.energy_min,
        energy_max=playlist.energy_max,
        valence_min=playlist.valence_min,
        valence_max=playlist.valence_max,
        danceability_min=playlist.danceability_min,
        danceability_max=playlist.danceability_max
    )
    
    # Add include tags
    if playlist.include_tag_ids:
        include_tags = db.query(Tag).filter(Tag.id.in_(playlist.include_tag_ids)).all()
        db_playlist.include_tags = include_tags
    
    # Add exclude tags
    if playlist.exclude_tag_ids:
        exclude_tags = db.query(Tag).filter(Tag.id.in_(playlist.exclude_tag_ids)).all()
        db_playlist.exclude_tags = exclude_tags
    
    # Add include groups
    if playlist.include_group_ids:
        include_groups = db.query(TagGroup).filter(TagGroup.id.in_(playlist.include_group_ids)).all()
        db_playlist.include_groups = include_groups
    
    # Add exclude groups
    if playlist.exclude_group_ids:
        exclude_groups = db.query(TagGroup).filter(TagGroup.id.in_(playlist.exclude_group_ids)).all()
        db_playlist.exclude_groups = exclude_groups
    
    db.add(db_playlist)
    db.commit()
    db.refresh(db_playlist)
    return db_playlist

@router.put("/{playlist_id}")
async def update_dynamic_playlist(
    playlist_id: int, 
    playlist_update: DynamicPlaylistUpdate, 
    db: Session = Depends(get_db)
):
    """Update a dynamic playlist."""
    playlist = db.query(DynamicPlaylist).filter(DynamicPlaylist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Dynamic playlist not found")
    
    # Update basic fields
    if playlist_update.name is not None:
        playlist.name = playlist_update.name
    if playlist_update.description is not None:
        playlist.description = playlist_update.description
    
    # Update audio feature filters
    if playlist_update.energy_min is not None:
        playlist.energy_min = playlist_update.energy_min
    if playlist_update.energy_max is not None:
        playlist.energy_max = playlist_update.energy_max
    if playlist_update.valence_min is not None:
        playlist.valence_min = playlist_update.valence_min
    if playlist_update.valence_max is not None:
        playlist.valence_max = playlist_update.valence_max
    if playlist_update.danceability_min is not None:
        playlist.danceability_min = playlist_update.danceability_min
    if playlist_update.danceability_max is not None:
        playlist.danceability_max = playlist_update.danceability_max
    
    # Update include tags
    if playlist_update.include_tag_ids is not None:
        include_tags = db.query(Tag).filter(Tag.id.in_(playlist_update.include_tag_ids)).all()
        playlist.include_tags = include_tags
    
    # Update exclude tags
    if playlist_update.exclude_tag_ids is not None:
        exclude_tags = db.query(Tag).filter(Tag.id.in_(playlist_update.exclude_tag_ids)).all()
        playlist.exclude_tags = exclude_tags
    
    # Update include groups
    if playlist_update.include_group_ids is not None:
        include_groups = db.query(TagGroup).filter(TagGroup.id.in_(playlist_update.include_group_ids)).all()
        playlist.include_groups = include_groups
    
    # Update exclude groups
    if playlist_update.exclude_group_ids is not None:
        exclude_groups = db.query(TagGroup).filter(TagGroup.id.in_(playlist_update.exclude_group_ids)).all()
        playlist.exclude_groups = exclude_groups
    
    db.commit()
    db.refresh(playlist)
    return playlist

@router.post("/{playlist_id}/rescan")
async def rescan_dynamic_playlist(playlist_id: int, db: Session = Depends(get_db)):
    """Rescan and regenerate songs for a dynamic playlist based on current tag assignments."""
    playlist = db.query(DynamicPlaylist).filter(DynamicPlaylist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Dynamic playlist not found")
    
    # Get the current songs that match the criteria (same logic as get_dynamic_playlist_songs)
    query = db.query(Song)
    
    # Include songs that have ANY of the include tags
    if playlist.include_tags:
        include_tag_ids = [tag.id for tag in playlist.include_tags]
        query = query.join(Song.tags).filter(Tag.id.in_(include_tag_ids))
    
    # Exclude songs that have ANY of the exclude tags
    if playlist.exclude_tags:
        exclude_tag_ids = [tag.id for tag in playlist.exclude_tags]
        exclude_songs = db.query(Song).join(Song.tags).filter(Tag.id.in_(exclude_tag_ids)).subquery()
        query = query.filter(~Song.id.in_(db.query(exclude_songs.c.id)))
    
    # Apply audio feature filters
    if playlist.energy_min is not None:
        query = query.filter(Song.energy >= playlist.energy_min)
    if playlist.energy_max is not None:
        query = query.filter(Song.energy <= playlist.energy_max)
    if playlist.valence_min is not None:
        query = query.filter(Song.valence >= playlist.valence_min)
    if playlist.valence_max is not None:
        query = query.filter(Song.valence <= playlist.valence_max)
    if playlist.danceability_min is not None:
        query = query.filter(Song.danceability >= playlist.danceability_min)
    if playlist.danceability_max is not None:
        query = query.filter(Song.danceability <= playlist.danceability_max)

    current_matching_songs = query.distinct().all()
    
    # Filter out songs with missing/invalid files
    valid_songs = []
    songs_to_remove = []
    
    for song in current_matching_songs:
        if not os.path.exists(song.file_path):
            songs_to_remove.append(song)
        else:
            try:
                file_size = os.path.getsize(song.file_path)
                if file_size == 0:
                    songs_to_remove.append(song)
                else:
                    valid_songs.append(song)
            except OSError:
                songs_to_remove.append(song)
    
    # Clean up invalid songs
    if songs_to_remove:
        for song in songs_to_remove:
            song.tags.clear()
            db.delete(song)
        db.commit()
    
    return {
        "message": f"Playlist '{playlist.name}' rescanned successfully",
        "total_songs": len(valid_songs),
        "removed_invalid_songs": len(songs_to_remove),
        "songs": valid_songs
    }

@router.delete("/{playlist_id}")
async def delete_dynamic_playlist(playlist_id: int, db: Session = Depends(get_db)):
    """Delete a dynamic playlist."""
    playlist = db.query(DynamicPlaylist).filter(DynamicPlaylist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Dynamic playlist not found")
    
    db.delete(playlist)
    db.commit()
    return {"message": "Dynamic playlist deleted"}
