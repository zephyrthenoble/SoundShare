from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional
from pydantic import BaseModel
import os

from database.database import get_db
from database.models import Playlist, Song

router = APIRouter()

class PlaylistCreate(BaseModel):
    name: str
    description: Optional[str] = None

class PlaylistUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class SongOrderUpdate(BaseModel):
    song_ids: List[int]

@router.get("/")
async def get_playlists(db: Session = Depends(get_db)):
    """Get all playlists."""
    playlists = db.query(Playlist).options(selectinload(Playlist.songs)).all()
    return playlists

@router.get("/{playlist_id}")
async def get_playlist(playlist_id: int, db: Session = Depends(get_db)):
    """Get a specific playlist with its songs, removing any songs whose files no longer exist or are zero-length."""
    playlist = db.query(Playlist).options(selectinload(Playlist.songs)).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    # Check each song's file existence and collect songs to remove
    songs_to_remove = []
    valid_songs = []
    
    for song in playlist.songs:
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
        
        print(f"Cleaned up {len(songs_to_remove)} songs with missing/zero-length files from playlist")
    
    # Update the playlist songs to only include valid ones
    playlist.songs = valid_songs
    
    return playlist

@router.get("/{playlist_id}/songs")
async def get_playlist_songs(playlist_id: int, db: Session = Depends(get_db)):
    """Get songs that belong to the playlist, removing any songs whose files no longer exist or are zero-length."""
    playlist = db.query(Playlist).options(selectinload(Playlist.songs)).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    # Check each song's file existence and collect songs to remove
    songs_to_remove = []
    valid_songs = []
    
    for song in playlist.songs:
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
        
        print(f"Cleaned up {len(songs_to_remove)} songs with missing/zero-length files from playlist")
    
    return valid_songs

@router.post("/")
async def create_playlist(playlist: PlaylistCreate, db: Session = Depends(get_db)):
    """Create a new playlist."""
    db_playlist = Playlist(**playlist.model_dump())
    db.add(db_playlist)
    db.commit()
    db.refresh(db_playlist)
    return db_playlist

@router.put("/{playlist_id}")
async def update_playlist(
    playlist_id: int, 
    playlist_update: PlaylistUpdate, 
    db: Session = Depends(get_db)
):
    """Update a playlist."""
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    update_data = playlist_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(playlist, field, value)
    
    db.commit()
    db.refresh(playlist)
    return playlist

@router.post("/{playlist_id}/songs/{song_id}")
async def add_song_to_playlist(
    playlist_id: int, 
    song_id: int, 
    db: Session = Depends(get_db)
):
    """Add a song to a playlist."""
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    song = db.query(Song).filter(Song.id == song_id).first()
    
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    
    if song not in playlist.songs:
        playlist.songs.append(song)
        db.commit()
    
    return {"message": "Song added to playlist"}

@router.delete("/{playlist_id}/songs/{song_id}")
async def remove_song_from_playlist(
    playlist_id: int, 
    song_id: int, 
    db: Session = Depends(get_db)
):
    """Remove a song from a playlist."""
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    song = db.query(Song).filter(Song.id == song_id).first()
    
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    
    if song in playlist.songs:
        playlist.songs.remove(song)
        db.commit()
    
    return {"message": "Song removed from playlist"}

@router.put("/{playlist_id}/order")
async def update_playlist_order(playlist_id: int, order_update: SongOrderUpdate, db: Session = Depends(get_db)):
    """Update the order of songs in a playlist."""
    playlist = db.query(Playlist).options(selectinload(Playlist.songs)).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    # Get songs in the new order
    ordered_songs = []
    for song_id in order_update.song_ids:
        song = db.query(Song).filter(Song.id == song_id).first()
        if song and song in playlist.songs:
            ordered_songs.append(song)
    
    # Update the playlist songs in the new order
    playlist.songs = ordered_songs
    db.commit()
    
    return {"message": "Playlist order updated"}

@router.delete("/{playlist_id}")
async def delete_playlist(playlist_id: int, db: Session = Depends(get_db)):
    """Delete a playlist."""
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    db.delete(playlist)
    db.commit()
    return {"message": "Playlist deleted"}
