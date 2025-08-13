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

async def _analyze_and_create_song(file_path: str, manually_added: bool = True):
    """
    Analyze a single audio file and create a Song object with full metadata.
    Returns (song, error) tuple where one will be None.
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            return None, f"File not found: {file_path}"

        # Check if it's an audio file
        valid_extensions = AUDIO_EXTENSIONS
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in valid_extensions:
            return None, f"Invalid audio file format: {file_path}"

        # Check file size - reject zero-length files
        file_info = Path(file_path)
        file_size = file_info.stat().st_size
        if file_size == 0:
            return None, f"File '{file_path}' is empty (0 bytes) and cannot be added"

        # Analyze audio and extract metadata
        try:
            analysis = audio_analyzer.analyze_song(file_path)
        except Exception as e:
            return None, f"Failed to analyze audio for {file_path}: {str(e)}"
        
        # Get filename
        filename = file_info.name
        
        # Use metadata title if available, otherwise use parsed title or filename
        final_display_name = (
            analysis.get('title') or
            analysis.get('parsed_title') or
            filename
        )
        
        # Extract year from date if it's a full date
        year_value = analysis.get('year')
        if year_value and isinstance(year_value, str):
            try:
                year_value = int(year_value.split('-')[0])
            except (ValueError, IndexError):
                year_value = None
        elif year_value:
            try:
                year_value = int(year_value)
            except (ValueError, TypeError):
                year_value = None
        
        # Get track number from metadata or filename parsing
        track_number = (
            analysis.get('track') or 
            analysis.get('parsed_track')
        )
        
        # Create song record with full metadata
        song = Song(
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
        
        print(f"Analyzed song: {final_display_name} from {file_path}")
        return song, None
        
    except Exception as e:
        return None, f"Unexpected error processing {file_path}: {str(e)}"

async def _create_songs_from_paths(file_paths: List[str], db: Session, manually_added: bool = True):
    """
    Shared function to create song records from file paths with full metadata analysis.
    Returns (added_songs, errors) tuple.
    """
    added_songs = []
    errors = []

    print(f"Processing {len(file_paths)} file paths, manually_added={manually_added}")
    
    for file_path in file_paths:
        # Check if song already exists
        existing_song = db.query(Song).filter(Song.file_path == file_path).first()
        if existing_song:
            errors.append(f"Song already exists in database: {file_path}")
            continue

        # Analyze and create song
        song, error = await _analyze_and_create_song(file_path, manually_added)
        if error:
            errors.append(error)
        else:
            added_songs.append(song)

    return added_songs, errors

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
    """Get all songs with their tags, removing any songs whose files no longer exist."""
    return _validate_and_clean_songs(db)

@router.get("/with-folders")
async def get_songs_with_folders(db: Session = Depends(get_db)):
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
    song = db.query(Song).options(selectinload(Song.tags)).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    return song

@router.post("/add")
async def add_song_file(
    songs: AddSongsRequest,
    db: Session = Depends(get_db)
):
    """
    Add songs by referencing existing file paths.
    """
    print("Starting song addition process")
    
    # Use shared function to create songs with full metadata
    added_songs, errors = await _create_songs_from_paths(songs.songs, db, manually_added=True)
    
    # Add all songs to database
    for song in added_songs:
        db.add(song)
    
    db.commit()
    
    # Refresh all songs to get their IDs
    for song in added_songs:
        db.refresh(song)
    
    print("Added:", len(added_songs))
    print("Errors:", len(errors))
    if errors:
        print("Error details:")
        for error in errors:
            print(f" - {error}")
    
    return {"found": 0, "added": len(added_songs), "errors": len(errors)}

@router.post("/remove")
async def remove_songs(
    songs: RemoveSongsRequest,
    db: Session = Depends(get_db)
):
    """
    Remove songs by file paths (for undo functionality).
    """
    removed = 0
    errors = []
    if len(songs.paths) == 0:
        raise HTTPException(status_code=400, detail="No song paths provided")
    print(f"Removing songs: {songs.paths}")
    for file_path in songs.paths:
        # Find song by file path
        existing_song = db.query(Song).filter(Song.file_path == file_path).first()
        if existing_song:
            db.delete(existing_song)
            removed += 1
        else:
            errors.append(f"Song not found in database: {file_path}")

    db.commit()
    print(f"Removed songs: {removed}")
    print(f"Errors: {errors}")
    return {"removed": removed, "errors": errors}

@router.post("/remove-by-id")
async def remove_songs_by_id(
    songs: RemoveSongsByIdRequest,
    db: Session = Depends(get_db)
):
    """
    Remove songs by IDs (more reliable than file paths).
    """
    removed = 0
    errors = []
    removed_paths = []
    
    if len(songs.ids) == 0:
        raise HTTPException(status_code=400, detail="No song IDs provided")
    
    print(f"Removing songs by ID: {songs.ids}")
    
    for song_id in songs.ids:
        # Find song by ID
        existing_song = db.query(Song).filter(Song.id == song_id).first()
        if existing_song:
            removed_paths.append(existing_song.file_path)  # Store path for undo
            db.delete(existing_song)
            removed += 1
            print(f"Removed song ID {song_id}: {existing_song.file_path}")
        else:
            errors.append(f"Song not found with ID: {song_id}")
            print(f"Song not found with ID: {song_id}")

    db.commit()
    print(f"Removed songs: {removed}")
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

@router.post("/upload-file", deprecated=True)
async def upload_song_file(
    file: UploadFile,
    display_name: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload a song file and add it to the database."""
    
    # Check if it's an audio file
    valid_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.wma'}
    file_ext = Path(file.filename or '').suffix.lower()
    if file_ext not in valid_extensions:
        raise HTTPException(status_code=400, detail="Invalid audio file format")
    
    # Create uploads directory if it doesn't exist
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    
    # Save the uploaded file
    filename = file.filename or 'unknown'
    file_path = uploads_dir / filename
    
    # Check if file already exists
    if file_path.exists():
        # Generate a unique filename
        stem = file_path.stem
        suffix = file_path.suffix
        counter = 1
        while file_path.exists():
            file_path = uploads_dir / f"{stem}_{counter}{suffix}"
            counter += 1
    
    # Save the file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Check if song already exists in database
    existing_song = db.query(Song).filter(Song.file_path == str(file_path)).first()
    if existing_song:
        # Remove the uploaded file since it already exists
        file_path.unlink()
        raise HTTPException(status_code=409, detail="Song already exists in database")
    
    # Check file size
    file_size = file_path.stat().st_size
    if file_size == 0:
        file_path.unlink()
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    
    # Analyze audio and extract metadata
    try:
        analysis = audio_analyzer.analyze_song(str(file_path))
    except Exception as e:
        file_path.unlink()  # Clean up on error
        raise HTTPException(status_code=500, detail=f"Failed to analyze audio: {str(e)}")
    
    # Use metadata title if available, otherwise use parsed title or filename
    final_display_name = display_name
    if not final_display_name:
        final_display_name = (
            analysis.get('title') or 
            analysis.get('parsed_title') or 
            file.filename
        )
    
    # Extract year from date if it's a full date
    year_value = analysis.get('year')
    if year_value and isinstance(year_value, str):
        try:
            year_value = int(year_value.split('-')[0])
        except (ValueError, IndexError):
            year_value = None
    elif year_value:
        try:
            year_value = int(year_value)
        except (ValueError, TypeError):
            year_value = None
    
    # Get track number from metadata or filename parsing
    track_number = (
        analysis.get('track') or 
        analysis.get('parsed_track')
    )
    
    # Create song record
    song = Song(
        filename=file.filename,
        display_name=final_display_name,
        file_path=str(file_path),
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
        track_number=track_number
    )
    
    db.add(song)
    db.commit()
    db.refresh(song)
    
    return song

@router.post("/upload-multiple")
async def upload_multiple_songs(
    files: List[UploadFile],
    db: Session = Depends(get_db)
):
    """Upload multiple song files and add them to the database."""
    
    added_songs = []
    errors = []
    
    # Create uploads directory if it doesn't exist
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    
    for file in files:
        try:
            # Check if it's an audio file
            valid_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.wma'}
            file_ext = Path(file.filename or '').suffix.lower()
            if file_ext not in valid_extensions:
                errors.append(f"{file.filename}: Invalid audio file format")
                continue
            
            # Save the uploaded file
            filename = file.filename or 'unknown'
            file_path = uploads_dir / filename
            
            # Generate unique filename if needed
            if file_path.exists():
                stem = file_path.stem
                suffix = file_path.suffix
                counter = 1
                while file_path.exists():
                    file_path = uploads_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
            
            # Save the file
            try:
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
            except Exception as e:
                errors.append(f"{file.filename}: Failed to save file - {str(e)}")
                continue
            
            # Check file size
            file_size = file_path.stat().st_size
            if file_size == 0:
                file_path.unlink()
                errors.append(f"{file.filename}: File is empty")
                continue
            
            # Check if song already exists in database
            existing_song = db.query(Song).filter(Song.file_path == str(file_path)).first()
            if existing_song:
                file_path.unlink()
                errors.append(f"{file.filename}: Song already exists in database")
                continue
            
            # Analyze audio and extract metadata
            try:
                analysis = audio_analyzer.analyze_song(str(file_path))
            except Exception as e:
                file_path.unlink()
                errors.append(f"{file.filename}: Failed to analyze audio - {str(e)}")
                continue
            
            # Use metadata title if available, otherwise use parsed title or filename
            final_display_name = (
                analysis.get('title') or 
                analysis.get('parsed_title') or 
                file.filename
            )
            
            # Extract year from date if it's a full date
            year_value = analysis.get('year')
            if year_value and isinstance(year_value, str):
                try:
                    year_value = int(year_value.split('-')[0])
                except (ValueError, IndexError):
                    year_value = None
            elif year_value:
                try:
                    year_value = int(year_value)
                except (ValueError, TypeError):
                    year_value = None
            
            # Get track number from metadata or filename parsing
            track_number = (
                analysis.get('track') or 
                analysis.get('parsed_track')
            )
            
            # Create song record
            song = Song(
                filename=file.filename,
                display_name=final_display_name,
                file_path=str(file_path),
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
                track_number=track_number
            )
            
            db.add(song)
            added_songs.append(song)
            
        except Exception as e:
            errors.append(f"{file.filename}: Unexpected error - {str(e)}")
    
    # Commit all successful additions
    if added_songs:
        db.commit()
        for song in added_songs:
            db.refresh(song)
    
    return {
        "added_songs": added_songs,
        "errors": errors,
        "summary": f"Uploaded {len(added_songs)} songs, {len(errors)} errors"
    }

@router.post("/add-multiple")
async def add_multiple_songs(
    file_paths: List[str],
    db: Session = Depends(get_db)
):
    """Add multiple songs by referencing existing file paths."""
    
    added_songs = []
    errors = []
    
    for file_path in file_paths:
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                errors.append(f"{file_path}: File not found")
                continue
            
            # Check if it's an audio file
            valid_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.wma'}
            file_ext = Path(file_path).suffix.lower()
            if file_ext not in valid_extensions:
                errors.append(f"{file_path}: Invalid audio file format")
                continue
            
            # Check if song already exists
            existing_song = db.query(Song).filter(Song.file_path == file_path).first()
            if existing_song:
                errors.append(f"{file_path}: Song already exists in database")
                continue
            
            # Get file info and check size
            file_info = Path(file_path)
            file_size = file_info.stat().st_size
            if file_size == 0:
                errors.append(f"{file_path}: File is empty (0 bytes)")
                continue
            
            # Analyze audio and extract metadata
            try:
                analysis = audio_analyzer.analyze_song(file_path)
            except Exception as e:
                errors.append(f"{file_path}: Failed to analyze audio - {str(e)}")
                continue
            
            # Get filename (file_info already retrieved above for size check)
            filename = file_info.name
            
            # Use metadata title if available, otherwise use parsed title or filename
            final_display_name = (
                analysis.get('title') or 
                analysis.get('parsed_title') or 
                filename
            )
            
            # Extract year from date if it's a full date
            year_value = analysis.get('year')
            if year_value and isinstance(year_value, str):
                try:
                    year_value = int(year_value.split('-')[0])
                except (ValueError, IndexError):
                    year_value = None
            elif year_value:
                try:
                    year_value = int(year_value)
                except (ValueError, TypeError):
                    year_value = None
            
            # Get track number from metadata or filename parsing
            track_number = (
                analysis.get('track') or 
                analysis.get('parsed_track')
            )
            
            # Create song record
            song = Song(
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
                track_number=track_number
            )
            
            db.add(song)
            added_songs.append(song)
            
        except Exception as e:
            errors.append(f"{file_path}: Unexpected error - {str(e)}")
    
    # Commit all successful additions
    if added_songs:
        db.commit()
        for song in added_songs:
            db.refresh(song)
    
    return {
        "added_songs": added_songs,
        "errors": errors,
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
    
    # Check if directory has been scanned before
    existing_scan = db.query(ScannedDirectory).filter(
        ScannedDirectory.directory_path == request.directory_path
    ).first()
    
    # Find audio files
    valid_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.wma'}
    audio_files = []
    
    if request.recursive:
        for root, dirs, files in os.walk(request.directory_path):
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
        for file in os.listdir(request.directory_path):
            file_path = os.path.join(request.directory_path, file)
            if os.path.isfile(file_path) and Path(file).suffix.lower() in valid_extensions:
                # Check file size - skip zero-length files
                try:
                    if os.path.getsize(file_path) > 0:
                        audio_files.append(file_path)
                except OSError:
                    continue  # Skip files we can't read
    
    if not audio_files:
        # Update or create scan record
        if existing_scan:
            existing_scan.last_scanned = datetime.utcnow()
            existing_scan.songs_found = 0
            existing_scan.songs_added = 0
            existing_scan.errors_count = 0
        else:
            new_scan = ScannedDirectory(
                directory_path=request.directory_path,
                recursive=request.recursive,
                songs_found=0,
                songs_added=0,
                errors_count=0
            )
            db.add(new_scan)
        
        db.commit()
        return {
            "added_songs": [],
            "errors": [],
            "summary": "No valid audio files found in directory"
        }
    
    # Add the found files using the multiple songs endpoint logic
    added_songs = []
    errors = []
    
    for file_path in audio_files:
        try:
            # Check if song already exists
            existing_song = db.query(Song).filter(Song.file_path == file_path).first()
            if existing_song:
                continue  # Skip existing songs
            
            # Get file info
            file_info = Path(file_path)
            file_size = file_info.stat().st_size
            
            # Skip zero-length files
            if file_size == 0:
                errors.append(f"{file_path}: File is empty (0 bytes)")
                continue
            
            # Analyze audio and extract metadata
            try:
                analysis = audio_analyzer.analyze_song(file_path)
            except Exception as e:
                errors.append(f"{file_path}: Failed to analyze audio - {str(e)}")
                continue
            
            filename = file_info.name
            
            # Use metadata title if available, otherwise use parsed title or filename
            final_display_name = (
                analysis.get('title') or 
                analysis.get('parsed_title') or 
                filename
            )
            
            # Extract year from date if it's a full date
            year_value = analysis.get('year')
            if year_value and isinstance(year_value, str):
                try:
                    year_value = int(year_value.split('-')[0])
                except (ValueError, IndexError):
                    year_value = None
            elif year_value:
                try:
                    year_value = int(year_value)
                except (ValueError, TypeError):
                    year_value = None
            
            # Get track number from metadata or filename parsing
            track_number = (
                analysis.get('track') or 
                analysis.get('parsed_track')
            )
            
            # Create song record
            song = Song(
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
                track_number=track_number
            )
            
            db.add(song)
            added_songs.append(song)
            
        except Exception as e:
            errors.append(f"{file_path}: Unexpected error - {str(e)}")
    
    # Commit all successful additions
    if added_songs:
        db.commit()
        for song in added_songs:
            db.refresh(song)
    
    # Update or create scan record
    if existing_scan:
        existing_scan.last_scanned = datetime.utcnow()
        existing_scan.songs_found = len(audio_files)
        existing_scan.songs_added = len(added_songs)
        existing_scan.errors_count = len(errors)
    else:
        new_scan = ScannedDirectory(
            directory_path=request.directory_path,
            recursive=request.recursive,
            songs_found=len(audio_files),
            songs_added=len(added_songs),
            errors_count=len(errors)
        )
        db.add(new_scan)
    
    db.commit()
    
    return {
        "added_songs": added_songs,
        "errors": errors,
        "summary": f"Scanned directory: {request.directory_path}. Found {len(audio_files)} files, added {len(added_songs)} songs, {len(errors)} errors",
        "is_rescan": existing_scan is not None
    }

@router.get("/scanned-directories")
async def get_scanned_directories(db: Session = Depends(get_db)):
    """Get list of previously scanned directories."""
    directories = db.query(ScannedDirectory).order_by(ScannedDirectory.last_scanned.desc()).all()
    return directories

@router.put("/{song_id}")
async def update_song(
    song_id: int,
    display_name: Optional[str] = None,
    artist: Optional[str] = None,
    album: Optional[str] = None,
    year: Optional[int] = None,
    genre: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Update song metadata."""
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    
    if display_name is not None:
        song.display_name = display_name
    if artist is not None:
        song.artist = artist
    if album is not None:
        song.album = album
    if year is not None:
        song.year = year
    if genre is not None:
        song.genre = genre
    
    db.commit()
    db.refresh(song)
    return song

@router.post("/{song_id}/tags/{tag_id}")
async def add_tag_to_song(song_id: int, tag_id: int, db: Session = Depends(get_db)):
    """Add a tag to a song."""
    song = db.query(Song).filter(Song.id == song_id).first()
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    if tag not in song.tags:
        song.tags.append(tag)
        db.commit()
    
    return {"message": "Tag added to song"}

@router.delete("/{song_id}/tags/{tag_id}")
async def remove_tag_from_song(song_id: int, tag_id: int, db: Session = Depends(get_db)):
    """Remove a tag from a song."""
    song = db.query(Song).filter(Song.id == song_id).first()
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    if tag in song.tags:
        song.tags.remove(tag)
        db.commit()
    
    return {"message": "Tag removed from song"}

@router.get("/{song_id}/preview")
async def get_song_preview(song_id: int, segment: int = 0, db: Session = Depends(get_db)):
    """Get a preview segment of a song (0-4 for the 5 segments)."""
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
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
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    
    file_path = song.file_path
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Song file not found")
    
    # Return the full audio file
    return FileResponse(
        file_path,
        media_type="audio/mpeg",
        headers={"Content-Disposition": f"inline; filename={song.display_name}.mp3"}
    )

@router.get("/{song_id}/stream")
async def stream_song(song_id: int, db: Session = Depends(get_db)):
    """Stream a song for media player playback."""
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    
    file_path = song.file_path
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Song file not found")
    
    # Return the audio file for streaming
    return FileResponse(
        file_path,
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

@router.post("/batch-tag")
async def batch_tag_songs(
    request: BatchTagRequest,
    db: Session = Depends(get_db)
):
    """Apply tags to multiple songs in batch."""
    
    if request.operation not in ["add", "replace", "remove"]:
        raise HTTPException(status_code=400, detail="Invalid operation. Must be 'add', 'replace', or 'remove'")
    
    # Get the songs
    songs = db.query(Song).filter(Song.id.in_(request.song_ids)).all()
    if not songs:
        raise HTTPException(status_code=404, detail="No songs found")
    
    # Get the tags
    tags = db.query(Tag).filter(Tag.id.in_(request.tag_ids)).all()
    if not tags:
        raise HTTPException(status_code=404, detail="No tags found")
    
    updated_count = 0
    
    for song in songs:
        if request.operation == "add":
            # Add tags (keep existing)
            for tag in tags:
                if tag not in song.tags:
                    song.tags.append(tag)
            updated_count += 1
            
        elif request.operation == "replace":
            # Replace all tags with selected ones
            song.tags = tags
            updated_count += 1
            
        elif request.operation == "remove":
            # Remove specified tags
            for tag in tags:
                if tag in song.tags:
                    song.tags.remove(tag)
            updated_count += 1
    
    db.commit()
    
    return {
        "message": f"Successfully {request.operation}ed tags for {updated_count} songs",
        "updated_count": updated_count,
        "operation": request.operation
    }
