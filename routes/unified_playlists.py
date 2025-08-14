from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import os

from database.database import get_db
from database.models import UnifiedPlaylist, DynamicCriteria, Song

router = APIRouter()

# Pydantic models for request/response
class DynamicCriteriaCreate(BaseModel):
    name: str
    include_criteria: Dict[str, Any] = {}
    exclude_criteria: Dict[str, Any] = {}
    order_index: int = 0

class DynamicCriteriaUpdate(BaseModel):
    name: Optional[str] = None
    include_criteria: Optional[Dict[str, Any]] = None
    exclude_criteria: Optional[Dict[str, Any]] = None
    order_index: Optional[int] = None

class UnifiedPlaylistCreate(BaseModel):
    name: str
    description: Optional[str] = None

class UnifiedPlaylistUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    song_order: Optional[List[int]] = None

class AddManualSongRequest(BaseModel):
    song_id: int

class ReorderSongsRequest(BaseModel):
    song_order: List[int]

# Unified Playlist CRUD endpoints
@router.get("/")
async def get_unified_playlists(db: Session = Depends(get_db)):
    """Get all unified playlists."""
    playlists = db.query(UnifiedPlaylist).options(
        selectinload(UnifiedPlaylist.manual_songs),
        selectinload(UnifiedPlaylist.dynamic_criteria)
    ).all()
    return playlists

@router.get("/{playlist_id}")
async def get_unified_playlist(playlist_id: int, db: Session = Depends(get_db)):
    """Get a specific unified playlist with all its data."""
    playlist = db.query(UnifiedPlaylist).options(
        selectinload(UnifiedPlaylist.manual_songs),
        selectinload(UnifiedPlaylist.dynamic_criteria)
    ).filter(UnifiedPlaylist.id == playlist_id).first()
    
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    return playlist

@router.post("/")
async def create_unified_playlist(playlist_data: UnifiedPlaylistCreate, db: Session = Depends(get_db)):
    """Create a new unified playlist."""
    playlist = UnifiedPlaylist(
        name=playlist_data.name,
        description=playlist_data.description,
        song_order=[]
    )
    
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    
    return playlist

@router.put("/{playlist_id}")
async def update_unified_playlist(
    playlist_id: int, 
    playlist_data: UnifiedPlaylistUpdate, 
    db: Session = Depends(get_db)
):
    """Update a unified playlist."""
    playlist = db.query(UnifiedPlaylist).filter(UnifiedPlaylist.id == playlist_id).first()
    
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    if playlist_data.name is not None:
        playlist.name = playlist_data.name
    if playlist_data.description is not None:
        playlist.description = playlist_data.description
    if playlist_data.song_order is not None:
        playlist.song_order = playlist_data.song_order
    
    db.commit()
    db.refresh(playlist)
    
    return playlist

@router.delete("/{playlist_id}")
async def delete_unified_playlist(playlist_id: int, db: Session = Depends(get_db)):
    """Delete a unified playlist."""
    playlist = db.query(UnifiedPlaylist).filter(UnifiedPlaylist.id == playlist_id).first()
    
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    db.delete(playlist)
    db.commit()
    
    return {"message": "Playlist deleted successfully"}

# Manual song management
@router.post("/{playlist_id}/manual-songs")
async def add_manual_song(
    playlist_id: int, 
    song_data: AddManualSongRequest, 
    db: Session = Depends(get_db)
):
    """Add a manual song to the playlist."""
    playlist = db.query(UnifiedPlaylist).filter(UnifiedPlaylist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    song = db.query(Song).filter(Song.id == song_data.song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    
    # Check if song is already in manual songs
    if song in playlist.manual_songs:
        raise HTTPException(status_code=400, detail="Song already in playlist")
    
    playlist.manual_songs.append(song)
    
    # Add to song order if not already there
    if song.id not in playlist.song_order:
        playlist.song_order.append(song.id)
    
    db.commit()
    db.refresh(playlist)
    
    return {"message": "Song added to playlist"}

@router.delete("/{playlist_id}/manual-songs/{song_id}")
async def remove_manual_song(playlist_id: int, song_id: int, db: Session = Depends(get_db)):
    """Remove a manual song from the playlist."""
    playlist = db.query(UnifiedPlaylist).filter(UnifiedPlaylist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    
    if song in playlist.manual_songs:
        playlist.manual_songs.remove(song)
    
    # Remove from song order
    if song_id in playlist.song_order:
        playlist.song_order.remove(song_id)
    
    db.commit()
    db.refresh(playlist)
    
    return {"message": "Song removed from playlist"}

# Song ordering
@router.put("/{playlist_id}/reorder")
async def reorder_songs(
    playlist_id: int, 
    reorder_data: ReorderSongsRequest, 
    db: Session = Depends(get_db)
):
    """Reorder songs in the playlist."""
    playlist = db.query(UnifiedPlaylist).filter(UnifiedPlaylist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    playlist.song_order = reorder_data.song_order
    db.commit()
    db.refresh(playlist)
    
    return {"message": "Songs reordered successfully"}

# Dynamic criteria management
@router.post("/{playlist_id}/criteria")
async def add_dynamic_criteria(
    playlist_id: int, 
    criteria_data: DynamicCriteriaCreate, 
    db: Session = Depends(get_db)
):
    """Add dynamic criteria to the playlist."""
    playlist = db.query(UnifiedPlaylist).filter(UnifiedPlaylist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    criteria = DynamicCriteria(
        playlist_id=playlist_id,
        name=criteria_data.name,
        include_criteria=criteria_data.include_criteria,
        exclude_criteria=criteria_data.exclude_criteria,
        order_index=criteria_data.order_index
    )
    
    db.add(criteria)
    db.commit()
    db.refresh(criteria)
    
    return criteria

@router.put("/{playlist_id}/criteria/{criteria_id}")
async def update_dynamic_criteria(
    playlist_id: int,
    criteria_id: int,
    criteria_data: DynamicCriteriaUpdate,
    db: Session = Depends(get_db)
):
    """Update dynamic criteria."""
    criteria = db.query(DynamicCriteria).filter(
        DynamicCriteria.id == criteria_id,
        DynamicCriteria.playlist_id == playlist_id
    ).first()
    
    if not criteria:
        raise HTTPException(status_code=404, detail="Criteria not found")
    
    if criteria_data.name is not None:
        criteria.name = criteria_data.name
    if criteria_data.include_criteria is not None:
        criteria.include_criteria = criteria_data.include_criteria
    if criteria_data.exclude_criteria is not None:
        criteria.exclude_criteria = criteria_data.exclude_criteria
    if criteria_data.order_index is not None:
        criteria.order_index = criteria_data.order_index
    
    db.commit()
    db.refresh(criteria)
    
    return criteria

@router.delete("/{playlist_id}/criteria/{criteria_id}")
async def delete_dynamic_criteria(
    playlist_id: int,
    criteria_id: int,
    db: Session = Depends(get_db)
):
    """Delete dynamic criteria."""
    criteria = db.query(DynamicCriteria).filter(
        DynamicCriteria.id == criteria_id,
        DynamicCriteria.playlist_id == playlist_id
    ).first()
    
    if not criteria:
        raise HTTPException(status_code=404, detail="Criteria not found")
    
    db.delete(criteria)
    db.commit()
    
    return {"message": "Criteria deleted successfully"}

# Get all songs for a playlist (manual + dynamic)
@router.get("/{playlist_id}/songs")
async def get_playlist_songs(playlist_id: int, db: Session = Depends(get_db)):
    """Get all songs in the playlist (manual + dynamic) in the correct order."""
    playlist = db.query(UnifiedPlaylist).options(
        selectinload(UnifiedPlaylist.manual_songs),
        selectinload(UnifiedPlaylist.dynamic_criteria)
    ).filter(UnifiedPlaylist.id == playlist_id).first()
    
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    # Get all songs that match dynamic criteria
    all_songs = db.query(Song).options(selectinload(Song.tags)).all()
    dynamic_songs = set()
    
    for criteria in playlist.dynamic_criteria:
        matching_songs = _apply_dynamic_criteria(all_songs, criteria)
        dynamic_songs.update(matching_songs)
    
    # Combine manual and dynamic songs
    manual_song_ids = {song.id for song in playlist.manual_songs}
    all_song_ids = manual_song_ids.union({song.id for song in dynamic_songs})
    
    # Get ordered song list
    ordered_songs = []
    songs_by_id = {song.id: song for song in all_songs if song.id in all_song_ids}
    
    # Add songs in the order specified, then append any unordered songs
    for song_id in playlist.song_order:
        if song_id in songs_by_id:
            ordered_songs.append(songs_by_id[song_id])
            del songs_by_id[song_id]
    
    # Add any remaining songs
    ordered_songs.extend(songs_by_id.values())
    
    return {
        "playlist": playlist,
        "songs": ordered_songs,
        "manual_count": len(manual_song_ids),
        "dynamic_count": len(dynamic_songs) - len(manual_song_ids.intersection({song.id for song in dynamic_songs})),
        "total_count": len(ordered_songs)
    }

def _apply_dynamic_criteria(songs: List[Song], criteria: DynamicCriteria) -> List[Song]:
    """Apply dynamic criteria to filter songs."""
    matching_songs = []
    
    for song in songs:
        if _song_matches_criteria(song, criteria):
            matching_songs.append(song)
    
    return matching_songs

def _song_matches_criteria(song: Song, criteria: DynamicCriteria) -> bool:
    """Check if a song matches the dynamic criteria."""
    include_criteria = criteria.include_criteria or {}
    exclude_criteria = criteria.exclude_criteria or {}
    
    # Check include criteria (song must match ALL include criteria)
    for field, values in include_criteria.items():
        if not _song_matches_field_criteria(song, field, values, is_include=True):
            return False
    
    # Check exclude criteria (song must NOT match ANY exclude criteria)
    for field, values in exclude_criteria.items():
        if _song_matches_field_criteria(song, field, values, is_include=False):
            return False
    
    return True

def _song_matches_field_criteria(song: Song, field: str, values: Any, is_include: bool) -> bool:
    """Check if a song matches criteria for a specific field."""
    if field == "tags":
        song_tag_ids = {tag.id for tag in song.tags}
        if isinstance(values, list):
            return bool(song_tag_ids.intersection(set(values)))
        return False
    
    elif field == "tag_groups":
        song_group_ids = {tag.group_id for tag in song.tags if tag.group_id}
        if isinstance(values, list):
            return bool(song_group_ids.intersection(set(values)))
        return False
    
    elif field in ["artists", "albums", "genres"]:
        song_value = getattr(song, field.rstrip('s'), None)  # Remove 's' for singular
        if isinstance(values, list):
            return song_value in values
        return False
    
    elif field in ["folders"]:
        # Extract folder from file_path
        song_folder = os.path.dirname(song.file_path) if song.file_path else ""
        if isinstance(values, list):
            return song_folder in values
        return False
    
    elif field in ["paths"]:
        if isinstance(values, list):
            return any(pattern in song.file_path for pattern in values)
        return False
    
    elif field in ["energy", "valence", "danceability", "tempo", "duration", "year"]:
        song_value = getattr(song, field, None)
        if song_value is not None and isinstance(values, dict):
            min_val = values.get("min")
            max_val = values.get("max")
            if min_val is not None and song_value < min_val:
                return False
            if max_val is not None and song_value > max_val:
                return False
            return True
        return False
    
    return False
