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

class BatchTagRequest(BaseModel):
    song_ids: List[int]
    tag_ids: List[int]
    operation: str  # "add", "replace", or "remove"

class ScanDirectoryRequest(BaseModel):
    directory_path: str
    recursive: bool = True

router = APIRouter()
audio_analyzer = AudioAnalyzer()

@router.get("/")
async def get_songs(db: Session = Depends(get_db)):
    """Get all songs with their tags, removing any songs whose files no longer exist."""
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

@router.get("/{song_id}")
async def get_song(song_id: int, db: Session = Depends(get_db)):
    """Get a specific song by ID."""
    song = db.query(Song).options(selectinload(Song.tags)).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    return song

@router.post("/add-file")
async def add_song_file(
    file_path: str,
    display_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Add a song by referencing an existing file path."""
    
    # Check if file exists
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if it's an audio file
    valid_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.wma'}
    file_ext = Path(file_path).suffix.lower()
    if file_ext not in valid_extensions:
        raise HTTPException(status_code=400, detail="Invalid audio file format")
    
    # Check if song already exists
    existing_song = db.query(Song).filter(Song.file_path == file_path).first()
    if existing_song:
        raise HTTPException(status_code=409, detail="Song already exists in database")
    
    # Check file size - reject zero-length files
    file_info = Path(file_path)
    file_size = file_info.stat().st_size
    if file_size == 0:
        raise HTTPException(status_code=400, detail=f"File '{file_path}' is empty (0 bytes) and cannot be added")
    
    # Analyze audio and extract metadata
    try:
        analysis = audio_analyzer.analyze_song(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze audio: {str(e)}")
    
    # Get filename (file_info already retrieved above for size check)
    filename = file_info.name
    
    # Use metadata title if available, otherwise use parsed title or filename
    final_display_name = display_name
    if not final_display_name:
        final_display_name = (
            analysis.get('title') or 
            analysis.get('parsed_title') or 
            filename
        )
    
    # Extract year from date if it's a full date
    year_value = analysis.get('year')
    if year_value and isinstance(year_value, str):
        try:
            # Try to extract year from date strings like "2023-01-01"
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
        file_size=file_info.stat().st_size,
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

@router.post("/upload-file")
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
