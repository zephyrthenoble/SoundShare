from fastapi import APIRouter, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from pydantic import BaseModel
from typing import List
from datetime import datetime, UTC
import os

from database.database import get_db
from database.models import Song, ScannedDirectory
from utils.config import get_library_path
from utils.constants import AUDIO_EXTENSIONS
from services.audio_analyzer import AudioAnalyzer

router = APIRouter()
templates = Jinja2Templates(directory="src/soundshare/templates")
audio_analyzer = AudioAnalyzer()

async def _analyze_and_create_song(file_path: str, manually_added: bool = False):
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

async def _create_songs_from_paths(file_paths: List[str], db: Session, manually_added: bool = False):
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

# Pydantic models for API requests
class AddSongRequest(BaseModel):
    path: str
    


class AddScanDirectoriesRequest(BaseModel):
    paths: List[str]

class RemoveScanDirectoriesRequest(BaseModel):
    paths: List[str]

class RemoveScanDirectoriesByIdRequest(BaseModel):
    ids: List[int]

class RemoveSongRequest(BaseModel):
    id: int

class ScanDirectoriesRequest(BaseModel):
    paths: List[str]

# Build a nested tree structure: {folder: {children:{...}, songs:[...]}}


@router.get("/")
async def get_library(db: Session = Depends(get_db)):
    manual = db.query(Song).filter(Song.manually_added == True).all()  # noqa: E712
    paths = db.query(ScannedDirectory).order_by(ScannedDirectory.last_scanned.desc()).all()
    # Build tree from all songs
    tree = {}
    for song in db.query(Song).all():
        # simpler tree: group by top-level folder
        p = Path(song.file_path)
        top = p.parent.name or p.parent.as_posix()
        entry = tree.setdefault(top, {"children": {}, "songs": []})
        entry["songs"].append({"id": song.id, "display_name": song.display_name})
    return {
        "manual_songs": manual,
        "paths": paths,
        "tree": tree
    }

@router.delete("/paths/{path_id}")
async def delete_path(path_id: int, db: Session = Depends(get_db)):
    path = db.query(ScannedDirectory).filter(ScannedDirectory.id == path_id).first()
    if not path:
        raise HTTPException(status_code=404, detail="Path not found")
    # Collect songs under path
    prefix = path.directory_path.rstrip("/\\")
    songs = db.query(Song).filter(Song.file_path.like(f"{prefix}%")).all()
    removed = 0
    for s in songs:
        if not s.manually_added:
            db.delete(s)
            removed += 1
    db.delete(path)
    db.commit()
    return {"message": "Path removed", "songs_removed": removed}

@router.get("/browse")
async def browse_library(path: str = "", db: Session = Depends(get_db)):
    """Browse files and directories within the library path (lazy loading)."""
    # Clean up the path parameter
    path = path.strip()
    
    try:
        library_root = get_library_path()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Library path configuration error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error getting library path: {str(e)}")
    
    # Determine target directory
    if not path or path == "":
        target_dir = library_root
    else:
        target_dir = library_root / path
        # Security check: ensure path is within library root
        try:
            target_dir = target_dir.resolve()
            library_root_resolved = library_root.resolve()
            if not str(target_dir).startswith(str(library_root_resolved)):
                raise HTTPException(status_code=403, detail="Path outside library root")
        except (OSError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid path: {str(e)}")
    
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {target_dir}")
    
    if not target_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Path is not a directory: {target_dir}")
    
    # Get existing songs and scanned directories for validation
    try:
        existing_songs = {song.file_path: song.id for song in db.query(Song).all()}
        existing_dirs = {dir.directory_path: dir.id for dir in db.query(ScannedDirectory).all()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    


    items = []
    try:
        for item in target_dir.iterdir():
            if item.name.startswith('.'):  # Skip hidden files
                continue
                
            try:
                relative_path = item.relative_to(library_root).as_posix()
                full_path = str(item)
                
                if item.is_dir():
                    items.append({
                        "type": "directory",
                        "name": item.name,
                        "path": relative_path,
                        "full_path": full_path,
                        "already_added": full_path in existing_dirs,
                        "id": existing_dirs.get(full_path)
                    })
                elif item.is_file() and item.suffix.lower() in AUDIO_EXTENSIONS:
                    items.append({
                        "type": "file", 
                        "name": item.name,
                        "path": relative_path,
                        "full_path": full_path,
                        "already_added": full_path in existing_songs,
                        "id": existing_songs.get(full_path)
                    })
            except Exception as e:
                # Skip items that cause errors but don't fail the whole request
                print(f"Error processing item {item}: {e}")
                continue
                
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied accessing directory")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading directory: {str(e)}")
    
    # Sort: directories first, then files, both alphabetically
    items.sort(key=lambda x: (x["type"] == "file", x["name"].lower()))
    
    parent_path = ""
    if target_dir != library_root:
        try:
            parent_path = str(target_dir.parent.relative_to(library_root)).replace("\\", "/")
            if parent_path == ".":
                parent_path = ""
        except ValueError:
            parent_path = ""
    
    return {
        "current_path": path,
        "items": items,
        "parent_path": parent_path
    }





# New API endpoints
@router.post("/song/add", deprecated=True)
async def add_song(request: AddSongRequest, db: Session = Depends(get_db)):
    """Add a single song to the database"""
    song_path = Path(request.path)
    
    # Check if song already exists
    existing = db.query(Song).filter(Song.file_path == str(song_path)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Song already exists")
    
    # Verify file exists and is in library path
    library_root = Path(get_library_path())
    try:
        song_path.resolve().relative_to(library_root.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="File is outside library path")
    
    if not song_path.exists():
        raise HTTPException(status_code=400, detail="File does not exist")
    
    # Create song record
    song = Song(
        file_path=str(song_path),
        display_name=song_path.stem,
        manually_added=True
    )
    
    db.add(song)
    db.commit()
    
    return {"message": "Song added successfully", "id": song.id}


@router.post("/directory/add")
async def add_scan_directories(request: AddScanDirectoriesRequest, db: Session = Depends(get_db)):
    """Add directories to scan list"""
    library_root = Path(get_library_path())
    added_dirs = []
    
    for dir_path in request.paths:
        path = Path(dir_path)
        
        # Verify directory is within library path
        try:
            path.resolve().relative_to(library_root.resolve())
        except ValueError:
            continue  # Skip directories outside library path
        
        if not path.exists() or not path.is_dir():
            continue  # Skip non-existent or non-directory paths
            
        # Check if already exists
        existing = db.query(ScannedDirectory).filter(ScannedDirectory.directory_path == str(path)).first()
        if existing:
            continue  # Skip already added directories
        
        # Add to database
        scan_dir = ScannedDirectory(
            directory_path=str(path),
            last_scanned=None
        )
        db.add(scan_dir)
        added_dirs.append(str(path))
    
    db.commit()
    return {"message": f"Added {len(added_dirs)} directories", "added": added_dirs}


@router.post("/directory/remove")
async def remove_scan_directories(request: RemoveScanDirectoriesRequest, db: Session = Depends(get_db)):
    """Remove directories from scan list (for undo functionality)"""
    removed_count = 0
    total_songs_removed = 0
    
    for dir_path in request.paths:
        scan_dir = db.query(ScannedDirectory).filter(ScannedDirectory.directory_path == dir_path).first()
        if scan_dir:
            # Remove songs under this directory path that were not manually added
            prefix = scan_dir.directory_path.rstrip("/\\")
            songs = db.query(Song).filter(Song.file_path.like(f"{prefix}%")).all()
            songs_removed = 0
            for s in songs:
                if not s.manually_added:
                    print(f"Removing song: {s.file_path} (from directory removal)")
                    db.delete(s)
                    songs_removed += 1
            
            total_songs_removed += songs_removed
            print(f"Removed {songs_removed} songs from directory: {dir_path}")
            
            # Remove the directory from scan list
            db.delete(scan_dir)
            removed_count += 1
    
    db.commit()
    return {"message": f"Removed {removed_count} directories and {total_songs_removed} songs"}

@router.post("/directory/remove-by-id")
async def remove_scan_directories_by_id(request: RemoveScanDirectoriesByIdRequest, db: Session = Depends(get_db)):
    """Remove directories from scan list by ID (more reliable than paths)"""
    removed_count = 0
    removed_paths = []
    errors = []
    total_songs_removed = 0
    removed_songs_data = []
    
    if len(request.ids) == 0:
        raise HTTPException(status_code=400, detail="No directory IDs provided")
    
    print(f"Removing directories by ID: {request.ids}")
    
    for dir_id in request.ids:
        scan_dir = db.query(ScannedDirectory).filter(ScannedDirectory.id == dir_id).first()
        if scan_dir:
            # Remove songs under this directory path that were not manually added
            prefix = scan_dir.directory_path.rstrip("/\\")
            songs = db.query(Song).filter(Song.file_path.like(f"{prefix}%")).all()
            songs_removed = 0
            songs_from_this_dir = []
            
            for s in songs:
                if not s.manually_added:
                    print(f"Removing song: {s.file_path} (from directory ID {dir_id} removal)")
                    songs_from_this_dir.append({
                        "id": s.id,
                        "file_path": s.file_path,
                        "display_name": s.display_name
                    })
                    db.delete(s)
                    songs_removed += 1
            
            total_songs_removed += songs_removed
            removed_songs_data.append({
                "directory_path": scan_dir.directory_path,
                "songs": songs_from_this_dir
            })
            print(f"Removed {songs_removed} songs from directory ID {dir_id}: {scan_dir.directory_path}")
            
            # Store path for undo functionality
            removed_paths.append(scan_dir.directory_path)
            
            # Remove the directory from scan list
            db.delete(scan_dir)
            removed_count += 1
            print(f"Removed directory ID {dir_id}: {scan_dir.directory_path}")
        else:
            errors.append(f"Directory not found with ID: {dir_id}")
            print(f"Directory not found with ID: {dir_id}")
    
    db.commit()
    print(f"Removed directories: {removed_count}")
    print(f"Removed songs: {total_songs_removed}")
    print(f"Errors: {errors}")
    return {
        "message": f"Removed {removed_count} directories and {total_songs_removed} songs", 
        "removed": removed_count, 
        "songs_removed": total_songs_removed,
        "errors": errors, 
        "removed_paths": removed_paths,
        "removed_songs_data": removed_songs_data
    }

@router.post("/scan")
async def scan_directories(request: ScanDirectoriesRequest, db: Session = Depends(get_db)):
    return await scan_local_directories(request.paths, db)

@router.post("/scan/all")
async def scan_all_directories(db: Session = Depends(get_db)):
    """Scan all directories for new music files"""
    # Get all scanned directories
    scanned_dirs = db.query(ScannedDirectory).all()
    if not scanned_dirs:
        raise HTTPException(status_code=404, detail="No directories to scan")

    paths = [x.directory_path for x in scanned_dirs]
    

    return await scan_local_directories(paths, db)

async def scan_local_directories(paths: List[str], db: Session=Depends(get_db)):
    """Scan directories for new music files using comprehensive metadata analysis"""

    all_file_paths = []
    directory_errors = 0
    
    # First, collect all audio file paths from all directories
    for dir_path in paths:
        try:
            print(f"Scanning directory: {dir_path}")
            path = Path(dir_path)
            if not path.exists() or not path.is_dir():
                directory_errors += 1
                print(f"Directory does not exist or is not a directory: {dir_path}")
                continue
                
            # Recursively find audio files
            for file_path in path.rglob('*'):
                if file_path.suffix.lower() in AUDIO_EXTENSIONS:
                    all_file_paths.append(str(file_path))
                    print(f"Found audio file: {file_path}")
                            
        except Exception as e:
            directory_errors += 1
            print(f"Error scanning directory {dir_path}: {str(e)}")
    
    print(f"Found {len(all_file_paths)} audio files across {len(paths)} directories")
    
    # Use shared function to create songs with full metadata (not manually added)
    added_songs, file_errors = await _create_songs_from_paths(all_file_paths, db, manually_added=False)
    
    # Add all songs to database
    for song in added_songs:
        db.add(song)
    
    # Update last_scanned timestamp for the directories
    for dir_path in paths:
        scan_dir = db.query(ScannedDirectory).filter(ScannedDirectory.directory_path == dir_path).first()
        if scan_dir:
            scan_dir.last_scanned = datetime.now(tz=UTC)

    db.commit()
    
    # Refresh all songs to get their IDs
    for song in added_songs:
        db.refresh(song)
    
    total_errors = directory_errors + len(file_errors)
    
    print(f"Scan complete: Found {len(all_file_paths)} files, added {len(added_songs)} songs, {total_errors} errors")
    if file_errors:
        print("File processing errors:")
        for error in file_errors[:10]:  # Show first 10 errors
            print(f" - {error}")
        if len(file_errors) > 10:
            print(f" - ... and {len(file_errors) - 10} more errors")
    
    return {"found": len(all_file_paths), "added": len(added_songs), "errors": total_errors}
