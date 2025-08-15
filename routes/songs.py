from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session, selectinload
from typing import Optional, List
from pydantic import BaseModel
import os
from pathlib import Path
import io
from datetime import datetime
import shutil
import tempfile

from database.database import get_db
from database.models import Song, Tag, ScannedDirectory
from services.audio_analyzer import AudioAnalyzer
from utils.constants import AUDIO_EXTENSIONS


class RescanSongsRequest(BaseModel):
    song_ids: List[int]
    mode: str  # "overwrite" or "fill_missing"

class AddSongsRequest(BaseModel):
    songs: List[str]

class RemoveSongsRequest(BaseModel):
    paths: List[str]

class RemoveSongsByIdRequest(BaseModel):
    ids: List[int]

class BatchTagRequest(BaseModel):
    song_ids: List[int]
    tag_ids: List[int]
    operation: str  # "add", "replace", or "remove"

class ScanDirectoryRequest(BaseModel):
    directory_path: str
    recursive: bool = True

router = APIRouter()
audio_analyzer = AudioAnalyzer()

# Helper functions for tag operations
def _get_song_by_id(db: Session, song_id: int, load_tags: bool = False) -> Song:
    """Get a single song by ID with optional tag loading."""
    query = db.query(Song)
    if load_tags:
        query = query.options(selectinload(Song.tags))
    
    song = query.filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    return song

def _get_tag_by_id(db: Session, tag_id: int) -> Tag:
    """Get a single tag by ID."""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag

def _validate_file_exists(file_path: str):
    """Validate that a song file exists and handle cleanup if not."""
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Song file not found")

def _get_songs_by_ids(db: Session, song_ids: List[int]) -> List[Song]:
    """Get songs by IDs with tags preloaded."""
    songs = db.query(Song).options(selectinload(Song.tags)).filter(Song.id.in_(song_ids)).all()
    if not songs:
        raise HTTPException(status_code=404, detail="No songs found")
    return songs

def _get_tags_by_ids(db: Session, tag_ids: List[int]) -> List[Tag]:
    """Get tags by IDs and validate all exist."""
    if not tag_ids:
        return []
    
    tags = db.query(Tag).filter(Tag.id.in_(tag_ids)).all()
    if len(tags) != len(tag_ids):
        raise HTTPException(status_code=404, detail="Some tags not found")
    return tags

def _apply_tag_operation(song: Song, tags: List[Tag], operation: str, tag_ids_to_remove: List[int] = None):
    """Apply a tag operation to a single song."""
    if operation == "add":
        # Add tags (avoid duplicates)
        existing_tag_ids = {tag.id for tag in song.tags}
        for tag in tags:
            if tag.id not in existing_tag_ids:
                song.tags.append(tag)
    elif operation in ["remove"]:
        # Remove tags by IDs
        if tag_ids_to_remove:
            song.tags = [tag for tag in song.tags if tag.id not in tag_ids_to_remove]
        else:
            # Remove specific tag objects
            for tag in tags:
                if tag in song.tags:
                    song.tags.remove(tag)
    elif operation in ["overwrite", "replace"]:
        # Replace all tags
        song.tags.clear()
        song.tags.extend(tags)
    else:
        raise HTTPException(status_code=400, detail=f"Invalid operation: {operation}")

def _bulk_update_song_tags(db: Session, song_ids: List[int], tag_ids: List[int], operation: str) -> List[Song]:
    """Perform bulk tag operations on multiple songs."""
    # Validate operation
    valid_operations = ["add", "remove", "overwrite", "replace"]
    if operation not in valid_operations:
        raise HTTPException(status_code=400, detail=f"Invalid operation. Must be one of: {', '.join(valid_operations)}")
    
    # Get songs and tags
    songs = _get_songs_by_ids(db, song_ids)
    tags = _get_tags_by_ids(db, tag_ids)
    
    # Apply operation to each song
    for song in songs:
        _apply_tag_operation(song, tags, operation, tag_ids)
    
    db.commit()
    
    # Refresh all songs to get updated relationships
    for song in songs:
        db.refresh(song)
    
    return songs

def _remove_songs_helper(db: Session, songs_to_remove: List[Song]) -> tuple[int, List[str], List[str]]:
    """
    Helper function to remove songs from the database.
    Returns (removed_count, removed_paths, errors).
    """
    removed = 0
    errors = []
    removed_paths = []
    
    for song in songs_to_remove:
        try:
            removed_paths.append(song.file_path)  # Store path for undo functionality
            db.delete(song)
            removed += 1
            print(f"Removed song ID {song.id}: {song.file_path}")
        except Exception as e:
            errors.append(f"Failed to remove song ID {song.id}: {str(e)}")
            print(f"Error removing song ID {song.id}: {str(e)}")
    
    if songs_to_remove:
        try:
            db.commit()
            print(f"Successfully removed {removed} songs")
        except Exception as e:
            db.rollback()
            error_msg = f"Failed to commit song removals: {str(e)}"
            errors.append(error_msg)
            print(error_msg)
            removed = 0
            removed_paths = []
    
    return removed, removed_paths, errors

def _find_audio_files(directory_path: str, recursive: bool = True) -> List[str]:
    """
    Find all valid audio files in a directory.
    Returns list of file paths.
    """
    valid_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.wma'}
    audio_files = []
    
    if recursive:
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if Path(file).suffix.lower() in valid_extensions:
                    full_path = os.path.join(root, file)
                    # Check file size - skip zero-length files
                    try:
                        if os.path.getsize(full_path) > 0:
                            audio_files.append(full_path)
                    except OSError:
                        continue  # Skip files we can't read
    else:
        for file in os.listdir(directory_path):
            file_path = os.path.join(directory_path, file)
            if os.path.isfile(file_path) and Path(file).suffix.lower() in valid_extensions:
                # Check file size - skip zero-length files
                try:
                    if os.path.getsize(file_path) > 0:
                        audio_files.append(file_path)
                except OSError:
                    continue  # Skip files we can't read
    
    return audio_files

def _update_scan_record(db: Session, directory_path: str, recursive: bool, songs_found: int, songs_added: int, errors_count: int):
    """Update or create a scan directory record."""
    existing_scan = db.query(ScannedDirectory).filter(
        ScannedDirectory.directory_path == directory_path
    ).first()
    
    if existing_scan:
        existing_scan.last_scanned = datetime.utcnow()
        existing_scan.songs_found = songs_found
        existing_scan.songs_added = songs_added
        existing_scan.errors_count = errors_count
    else:
        new_scan = ScannedDirectory(
            directory_path=directory_path,
            recursive=recursive,
            songs_found=songs_found,
            songs_added=songs_added,
            errors_count=errors_count
        )
        db.add(new_scan)

def _validate_audio_file(file_path: str):
    """
    Validate if a file is a valid audio file.
    Returns (is_valid, error_message) tuple.
    """
    # Check if file exists
    if not os.path.exists(file_path):
        return False, "File not found"
    
    # Check if it's an audio file
    file_ext = Path(file_path).suffix.lower()
    if file_ext not in AUDIO_EXTENSIONS:
        return False, "Invalid audio file format"
    
    # Check file size - reject zero-length files
    try:
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return False, "File is empty (0 bytes)"
    except OSError:
        return False, "Cannot access file"
    
    return True, None

def _process_year_value(year_value):
    """
    Process year value from metadata, handling both string dates and integers.
    Returns integer year or None.
    """
    if year_value and isinstance(year_value, str):
        try:
            return int(year_value.split('-')[0])
        except (ValueError, IndexError):
            return None
    elif year_value:
        try:
            return int(year_value)
        except (ValueError, TypeError):
            return None
    return None

def _create_song_object_from_analysis(analysis: dict, file_path: str, manually_added: bool = True) -> Song:
    """
    Create a Song object from audio analysis data.
    """
    file_info = Path(file_path)
    filename = file_info.name
    file_size = file_info.stat().st_size
    
    # Use metadata title if available, otherwise use parsed title or filename
    final_display_name = (
        analysis.get('title') or
        analysis.get('parsed_title') or
        filename
    )
    
    # Process year value
    year_value = _process_year_value(analysis.get('year'))
    
    # Get track number from metadata or filename parsing
    track_number = (
        analysis.get('track') or 
        analysis.get('parsed_track')
    )
    
    # Create song record with full metadata
    return Song(
        filename=filename,
        display_name=final_display_name,
        file_path=file_path,
        file_size=file_size,
        duration=analysis.get('duration'),
        tempo=analysis.get('tempo'),
        key=analysis.get('key'),
        energy=analysis.get('energy', 0.5),
        valence=analysis.get('valence', 0.5),
        danceability=analysis.get('danceability', 0.5),
        artist=analysis.get('artist'),
        album=analysis.get('album'),
        year=year_value,
        genre=analysis.get('genre'),
        track_number=track_number,
        manually_added=manually_added
    )

async def _analyze_and_create_song(file_path: str, manually_added: bool = True):
    """
    Analyze a single audio file and create a Song object with full metadata.
    Returns (song, error) tuple where one will be None.
    """
    try:
        # Validate audio file
        is_valid, error_msg = _validate_audio_file(file_path)
        if not is_valid:
            return None, f"File '{file_path}': {error_msg}"

        # Analyze audio and extract metadata
        try:
            analysis = audio_analyzer.analyze_song(file_path)
        except Exception as e:
            return None, f"Failed to analyze audio for {file_path}: {str(e)}"
        
        song = _create_song_object_from_analysis(analysis, file_path, manually_added)
        print(f"Analyzed song: {song.display_name} from {file_path}")
        return song, None
        
    except Exception as e:
        return None, f"Unexpected error processing {file_path}: {str(e)}"


async def _create_song_from_file_path(file_path: str, db: Session, manually_added: bool = True, skip_existing: bool = True):
    """
    Create a song record from a file path with full validation and metadata analysis.
    Returns (song, error) tuple where one will be None.
    """
    try:
        # Validate audio file
        is_valid, error_msg = _validate_audio_file(file_path)
        if not is_valid:
            return None, f"{file_path}: {error_msg}"
        
        # Check if song already exists
        if skip_existing:
            existing_song = db.query(Song).filter(Song.file_path == file_path).first()
            if existing_song:
                return None, f"{file_path}: Song already exists in database"
        
        # Analyze audio and extract metadata
        try:
            analysis = audio_analyzer.analyze_song(file_path)
        except Exception as e:
            return None, f"{file_path}: Failed to analyze audio - {str(e)}"
        
        song = _create_song_object_from_analysis(analysis, file_path, manually_added)
        return song, None
        
    except Exception as e:
        return None, f"{file_path}: Unexpected error - {str(e)}"

def _validate_and_clean_songs(db: Session):
    """
    Helper function to validate song files and remove invalid ones.
    Returns a list of valid songs.
    """
    songs = db.query(Song).options(selectinload(Song.tags)).all()
    
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
    
    # Remove songs whose files don't exist
    if songs_to_remove:
        for song in songs_to_remove:
            # Clear all tag relationships (SQLAlchemy will handle the many-to-many cleanup)
            song.tags.clear()
            
            # Remove from any playlists (SQLAlchemy will handle the many-to-many cleanup)
            # The playlist_songs association table entries will be automatically removed
            
            # Delete the song itself
            db.delete(song)
        
        # Commit the deletions
        db.commit()
        
        print(f"Cleaned up {len(songs_to_remove)} songs with missing files")
    
    return valid_songs

@router.get("/")
async def get_songs(db: Session = Depends(get_db)):
    """Get all songs with their tags and properly extracted folder information using pathlib."""
    valid_songs = _validate_and_clean_songs(db)
    
    # Enhance songs with folder information using pathlib
    enhanced_songs = []
    for song in valid_songs:
        # Convert to dict
        song_dict = {
            "id": song.id,
            "filename": song.filename,
            "display_name": song.display_name,
            "file_path": song.file_path,
            "duration": song.duration,
            "file_size": song.file_size,
            "tempo": song.tempo,
            "key": song.key,
            "mode": song.mode,
            "energy": song.energy,
            "valence": song.valence,
            "danceability": song.danceability,
            "artist": song.artist,
            "album": song.album,
            "year": song.year,
            "genre": song.genre,
            "track_number": song.track_number,
            "created_at": song.created_at,
            "last_played": song.last_played,
            "updated_at": song.updated_at,
            "manually_added": song.manually_added,
            "tags": [{"id": tag.id, "name": tag.name} for tag in song.tags]
        }
        
        # Extract folder using pathlib
        try:
            file_path = Path(song.file_path)
            parent_folder = file_path.parent.name
            if not parent_folder:  # If it's root or empty
                parent_folder = str(file_path.parent)
            song_dict["folder"] = parent_folder
        except Exception as e:
            print(f"Error extracting folder for {song.file_path}: {e}")
            song_dict["folder"] = "Unknown"
        
        enhanced_songs.append(song_dict)
    
    return enhanced_songs


@router.get("/{song_id}")
async def get_song(song_id: int, db: Session = Depends(get_db)):
    """Get a specific song by ID."""
    return _get_song_by_id(db, song_id, load_tags=True)

@router.post("/remove")
async def remove_songs(
    songs: RemoveSongsRequest,
    db: Session = Depends(get_db)
):
    """
    Remove songs by file paths (for undo functionality).
    """
    if len(songs.paths) == 0:
        raise HTTPException(status_code=400, detail="No song paths provided")
    
    print(f"Removing songs by paths: {songs.paths}")
    
    # Find songs by file paths
    songs_to_remove = []
    not_found_paths = []
    
    for file_path in songs.paths:
        existing_song = db.query(Song).filter(Song.file_path == file_path).first()
        if existing_song:
            songs_to_remove.append(existing_song)
        else:
            not_found_paths.append(file_path)
    
    # Use helper function to remove songs
    removed, removed_paths, errors = _remove_songs_helper(db, songs_to_remove)
    
    # Add not found errors
    for path in not_found_paths:
        errors.append(f"Song not found in database: {path}")
    
    print(f"Removed songs: {removed}")
    if errors:
        print(f"Errors: {errors}")
    
    return {"removed": removed, "errors": errors, "removed_paths": removed_paths}

@router.post("/remove-by-id")
async def remove_songs_by_id(
    songs: RemoveSongsByIdRequest,
    db: Session = Depends(get_db)
):
    """
    Remove songs by IDs (more reliable than file paths).
    """
    if len(songs.ids) == 0:
        raise HTTPException(status_code=400, detail="No song IDs provided")
    
    print(f"Removing songs by ID: {songs.ids}")
    
    # Find songs by IDs
    songs_to_remove = []
    not_found_ids = []
    
    for song_id in songs.ids:
        existing_song = db.query(Song).filter(Song.id == song_id).first()
        if existing_song:
            songs_to_remove.append(existing_song)
        else:
            not_found_ids.append(song_id)
    
    # Use helper function to remove songs
    removed, removed_paths, errors = _remove_songs_helper(db, songs_to_remove)
    
    # Add not found errors
    for song_id in not_found_ids:
        errors.append(f"Song not found with ID: {song_id}")
        print(f"Song not found with ID: {song_id}")
    
    print(f"Removed songs: {removed}")
    if errors:
        print(f"Errors: {errors}")
    
    return {"removed": removed, "errors": errors, "removed_paths": removed_paths}

@router.post("/rescan")
async def rescan_songs(
    request: RescanSongsRequest,
    db: Session = Depends(get_db)
):
    """
    Rescan songs to update their metadata.
    Mode can be 'overwrite' (replace all metadata) or 'fill_missing' (only update empty fields).
    """
    if len(request.song_ids) == 0:
        raise HTTPException(status_code=400, detail="No song IDs provided")
    
    if request.mode not in ["overwrite", "fill_missing"]:
        raise HTTPException(status_code=400, detail="Mode must be 'overwrite' or 'fill_missing'")
    
    updated = 0
    errors = []
    
    print(f"Rescanning {len(request.song_ids)} songs with mode: {request.mode}")
    
    for song_id in request.song_ids:
        try:
            # Find existing song
            existing_song = db.query(Song).filter(Song.id == song_id).first()
            if not existing_song:
                errors.append(f"Song not found with ID: {song_id}")
                continue
            
            # Get fresh analysis
            fresh_song, error = await _analyze_and_create_song(existing_song.file_path, existing_song.manually_added)
            if error:
                errors.append(f"Failed to analyze song ID {song_id}: {error}")
                continue
            
            # Update metadata based on mode
            if request.mode == "overwrite":
                # Replace all metadata
                existing_song.display_name = fresh_song.display_name
                existing_song.duration = fresh_song.duration
                existing_song.tempo = fresh_song.tempo
                existing_song.key = fresh_song.key
                existing_song.energy = fresh_song.energy
                existing_song.valence = fresh_song.valence
                existing_song.danceability = fresh_song.danceability
                existing_song.artist = fresh_song.artist
                existing_song.album = fresh_song.album
                existing_song.year = fresh_song.year
                existing_song.genre = fresh_song.genre
                existing_song.track_number = fresh_song.track_number
                existing_song.file_size = fresh_song.file_size
                
            elif request.mode == "fill_missing":
                # Only update fields that are currently None or empty
                if not existing_song.display_name or existing_song.display_name == existing_song.filename:
                    existing_song.display_name = fresh_song.display_name
                if existing_song.duration is None:
                    existing_song.duration = fresh_song.duration
                if existing_song.tempo is None:
                    existing_song.tempo = fresh_song.tempo
                if existing_song.key is None:
                    existing_song.key = fresh_song.key
                if existing_song.energy is None:
                    existing_song.energy = fresh_song.energy
                if existing_song.valence is None:
                    existing_song.valence = fresh_song.valence
                if existing_song.danceability is None:
                    existing_song.danceability = fresh_song.danceability
                if not existing_song.artist:
                    existing_song.artist = fresh_song.artist
                if not existing_song.album:
                    existing_song.album = fresh_song.album
                if existing_song.year is None:
                    existing_song.year = fresh_song.year
                if not existing_song.genre:
                    existing_song.genre = fresh_song.genre
                if existing_song.track_number is None:
                    existing_song.track_number = fresh_song.track_number
                if existing_song.file_size is None:
                    existing_song.file_size = fresh_song.file_size
            
            updated += 1
            print(f"Updated song ID {song_id}: {existing_song.display_name}")
            
        except Exception as e:
            errors.append(f"Unexpected error rescanning song ID {song_id}: {str(e)}")
            print(f"Error rescanning song ID {song_id}: {str(e)}")
    
    db.commit()
    
    print(f"Rescan complete: Updated {updated} songs, {len(errors)} errors")
    if errors:
        print("Rescan errors:")
        for error in errors[:5]:  # Show first 5 errors
            print(f" - {error}")
        if len(errors) > 5:
            print(f" - ... and {len(errors) - 5} more errors")
    
    return {"updated": updated, "errors": errors}


@router.post("/add")
async def add_songs(
    songs: AddSongsRequest,
    db: Session = Depends(get_db)
):
    """Add multiple songs by referencing existing file paths."""
    
    added_songs = []
    errors = []
    
    for file_path in songs.songs:
        song, error = await _create_song_from_file_path(file_path, db, manually_added=True, skip_existing=True)
        if error:
            errors.append(error)
        else:
            db.add(song)
            added_songs.append(song)
    
    # Commit all successful additions
    if added_songs:
        db.commit()
        for song in added_songs:
            db.refresh(song)
    
    return {
        "found": 0,  # Keep for backward compatibility
        "added": len(added_songs),
        "errors": len(errors),
        "added_songs": added_songs,
        "summary": f"Added {len(added_songs)} songs, {len(errors)} errors"
    }

@router.post("/scan-directory")
async def scan_directory(
    request: ScanDirectoryRequest,
    db: Session = Depends(get_db)
):
    """Scan a directory for audio files and add them to the database."""
    
    if not os.path.exists(request.directory_path):
        raise HTTPException(status_code=404, detail="Directory not found")
    
    if not os.path.isdir(request.directory_path):
        raise HTTPException(status_code=400, detail="Path is not a directory")
    
    # Find audio files
    audio_files = _find_audio_files(request.directory_path, request.recursive)
    
    if not audio_files:
        # Update or create scan record
        _update_scan_record(db, request.directory_path, request.recursive, 0, 0, 0)
        db.commit()
        return {
            "added_songs": [],
            "errors": [],
            "summary": "No valid audio files found in directory"
        }
    
    # Add the found files using the shared song creation logic
    added_songs = []
    errors = []
    
    for file_path in audio_files:
        song, error = await _create_song_from_file_path(file_path, db, manually_added=False, skip_existing=True)
        if error:
            # Only append error if it's not about existing songs (we skip those silently)
            if "already exists" not in error:
                errors.append(error)
        else:
            db.add(song)
            added_songs.append(song)
    
    # Commit all successful additions
    if added_songs:
        db.commit()
        for song in added_songs:
            db.refresh(song)
    
    # Update or create scan record
    _update_scan_record(db, request.directory_path, request.recursive, len(audio_files), len(added_songs), len(errors))
    db.commit()
    
    return {
        "added_songs": added_songs,
        "errors": errors,
        "summary": f"Scanned directory: {request.directory_path}. Found {len(audio_files)} files, added {len(added_songs)} songs, {len(errors)} errors",
        "is_rescan": db.query(ScannedDirectory).filter(ScannedDirectory.directory_path == request.directory_path).first() is not None
    }



@router.put("/{song_id}")
async def update_song(
    song_id: int,
    display_name: Optional[str] = Form(None),
    artist: Optional[str] = Form(None),
    album: Optional[str] = Form(None),
    year: Optional[str] = Form(None),  # Accept as string to handle empty values
    genre: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Update song metadata."""
    song = _get_song_by_id(db, song_id)
    
    # Always update if parameter is provided (including empty strings)
    if display_name is not None:
        song.display_name = display_name
    if artist is not None:
        song.artist = artist if artist.strip() else None
    if album is not None:
        song.album = album if album.strip() else None
    if year is not None:
        # Handle year conversion from string to int
        if year and str(year).strip():
            try:
                song.year = int(year)
            except ValueError:
                raise HTTPException(status_code=400, detail="Year must be a valid integer")
        else:
            song.year = None
    if genre is not None:
        song.genre = genre if genre.strip() else None
    
    db.commit()
    db.refresh(song)
    return song

@router.post("/{song_id}/tags/{tag_id}")
async def add_tag_to_song(song_id: int, tag_id: int, db: Session = Depends(get_db)):
    """Add a tag to a song."""
    song = _get_song_by_id(db, song_id, load_tags=True)
    tag = _get_tag_by_id(db, tag_id)
    
    _apply_tag_operation(song, [tag], "add")
    db.commit()
    
    return {"message": "Tag added to song"}

@router.delete("/{song_id}/tags/{tag_id}")
async def remove_tag_from_song(song_id: int, tag_id: int, db: Session = Depends(get_db)):
    """Remove a tag from a song."""
    song = _get_song_by_id(db, song_id, load_tags=True)
    tag = _get_tag_by_id(db, tag_id)
    
    _apply_tag_operation(song, [tag], "remove")
    db.commit()
    
    return {"message": "Tag removed from song"}

class SongTagsUpdate(BaseModel):
    tag_ids: List[int]

class BulkTagUpdate(BaseModel):
    song_ids: List[int]
    tag_ids: List[int]
    operation: str  # "add", "remove", or "overwrite"

@router.put("/{song_id}/tags/batch")
async def update_song_tags_batch(song_id: int, request: SongTagsUpdate, db: Session = Depends(get_db)):
    """Update all tags for a song in batch (replaces existing tags)."""
    songs = _bulk_update_song_tags(db, [song_id], request.tag_ids, "overwrite")
    return songs[0]

@router.put("/bulk-tags")
async def update_bulk_tags(request: BulkTagUpdate, db: Session = Depends(get_db)):
    """Perform bulk tag operations on multiple songs."""
    updated_songs = _bulk_update_song_tags(db, request.song_ids, request.tag_ids, request.operation)
    return {"updated_songs": updated_songs}

@router.get("/{song_id}/preview")
async def get_song_preview(song_id: int, segment: int = 0, db: Session = Depends(get_db)):
    """Get a preview segment of a song (0-4 for the 5 segments)."""
    song = _get_song_by_id(db, song_id)
    print(f"song id: {song.id}")
    print(f"song file path: {song.file_path}")

    if not os.path.exists(song.file_path):
        await _delete_song(song_id, db)
        raise HTTPException(status_code=404, detail="Song file not found")
    
    print("found song")
    if segment < 0 or segment > 4:
        raise HTTPException(status_code=400, detail="Segment must be between 0 and 4")
    print("correct segment")
    
    # Generate preview segments
    segments = audio_analyzer.create_preview_segments(song.file_path)
    
    if segment >= len(segments):
        raise HTTPException(status_code=404, detail="Preview segment not available")
    
    print("segment found")
    # Return audio stream
    return StreamingResponse(
        io.BytesIO(segments[segment]),
        media_type="audio/wav",
        headers={"Content-Disposition": f"inline; filename=preview_{segment}.wav"}
    )

@router.get("/{song_id}/audio")
async def get_song_audio(song_id: int, db: Session = Depends(get_db)):
    """Get the full audio file for a song."""
    song = _get_song_by_id(db, song_id)
    _validate_file_exists(song.file_path)
    
    # Return the full audio file
    return FileResponse(
        song.file_path,
        media_type="audio/mpeg",
        headers={"Content-Disposition": f"inline; filename={song.display_name}.mp3"}
    )

@router.get("/{song_id}/stream")
async def stream_song(song_id: int, db: Session = Depends(get_db)):
    """Stream a song for media player playback."""
    song = _get_song_by_id(db, song_id)
    _validate_file_exists(song.file_path)
    
    # Return the audio file for streaming
    return FileResponse(
        song.file_path,
        media_type="audio/mpeg",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f"inline; filename={song.display_name}.mp3"
        }
    )

@router.delete("/{song_id}")
async def delete_song(song_id: int, db: Session = Depends(get_db)):
    """Remove a song from the system (but not from disk)."""
    await _delete_song(song_id, db)
    return {"message": "Song removed from system"}

async def _delete_song(song_id: int, db: Session = Depends(get_db)):
    """Remove a song from the system (but not from disk)."""
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    
    db.delete(song)
    db.commit()
    return {"message": "Song removed from system"}
