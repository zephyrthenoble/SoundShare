from fastapi import APIRouter, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from pydantic import BaseModel
from typing import List
from datetime import datetime, UTC

from database.database import get_db
from database.models import Song, ScannedDirectory
from utils.config import get_library_path
from utils.constants import AUDIO_EXTENSIONS

router = APIRouter()
templates = Jinja2Templates(directory="src/soundshare/templates")

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

def _insert_path(root, song):
    fp = Path(song.file_path)
    parts = fp.parts[:-1]  # exclude filename
    node = root
    for part in parts[-6:]:  # limit depth stored to last 6 parts to avoid huge roots
        node = node.setdefault(part, {"children": {}, "songs": []})["children"]
    # attach at parent of file
    parent_key = fp.parent.name or str(fp.parent)
    parent_node = root.setdefault(parent_key, {"children": {}, "songs": []}) if parent_key not in root else root[parent_key]
    parent_node.setdefault("songs", []).append({"id": song.id, "display_name": song.display_name})


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
    
    for dir_path in request.paths:
        scan_dir = db.query(ScannedDirectory).filter(ScannedDirectory.directory_path == dir_path).first()
        if scan_dir:
            db.delete(scan_dir)
            removed_count += 1
    
    db.commit()
    return {"message": f"Removed {removed_count} directories"}

@router.post("/directory/remove-by-id")
async def remove_scan_directories_by_id(request: RemoveScanDirectoriesByIdRequest, db: Session = Depends(get_db)):
    """Remove directories from scan list by ID (more reliable than paths)"""
    removed_count = 0
    removed_paths = []
    errors = []
    
    if len(request.ids) == 0:
        raise HTTPException(status_code=400, detail="No directory IDs provided")
    
    print(f"Removing directories by ID: {request.ids}")
    
    for dir_id in request.ids:
        scan_dir = db.query(ScannedDirectory).filter(ScannedDirectory.id == dir_id).first()
        if scan_dir:
            removed_paths.append(scan_dir.directory_path)  # Store path for undo
            db.delete(scan_dir)
            removed_count += 1
            print(f"Removed directory ID {dir_id}: {scan_dir.directory_path}")
        else:
            errors.append(f"Directory not found with ID: {dir_id}")
            print(f"Directory not found with ID: {dir_id}")
    
    db.commit()
    print(f"Removed directories: {removed_count}")
    print(f"Errors: {errors}")
    return {"message": f"Removed {removed_count} directories", "removed": removed_count, "errors": errors, "removed_paths": removed_paths}

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
    """Scan directories for new music files"""

    found = 0
    added = 0
    errors = 0
    
    for dir_path in paths:
        try:
            print(f"Scanning directory: {dir_path}")
            path = Path(dir_path)
            if not path.exists() or not path.is_dir():
                errors += 1
                continue
                
            # Recursively find audio files
            for file_path in path.rglob('*'):
                print(f"Found file: {file_path}")
                if file_path.suffix.lower() in AUDIO_EXTENSIONS:
                    found += 1
                    
                    # Check if already exists
                    existing = db.query(Song).filter(Song.file_path == str(file_path)).first()
                    if not existing:
                        try:
                            song = Song(
                                filename=file_path.name,
                                file_path=str(file_path),
                                display_name=file_path.stem,
                                manually_added=False
                            )
                            print(song)
                            db.add(song)
                            added += 1
                        except Exception:
                            errors += 1
                            
        except Exception:
            errors += 1
    
    # Update last_scanned timestamp for the directories
    for dir_path in paths:
        scan_dir = db.query(ScannedDirectory).filter(ScannedDirectory.directory_path == dir_path).first()
        if scan_dir:

            scan_dir.last_scanned = datetime.now(tz=UTC)

    db.commit()
    return {"found": found, "added": added, "errors": errors}
