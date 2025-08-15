from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Table, Text, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

# Association tables for many-to-many relationships
song_tags = Table(
    'song_tags',
    Base.metadata,
    Column('song_id', Integer, ForeignKey('songs.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)

class TagGroup(Base):
    __tablename__ = "tag_groups"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text)
    color = Column(String, default="#007bff")  # For UI grouping
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tags = relationship("Tag", back_populates="group", cascade="all, delete-orphan")

class Tag(Base):
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text)
    group_id = Column(Integer, ForeignKey("tag_groups.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    group = relationship("TagGroup", back_populates="tags")
    songs = relationship("Song", secondary=song_tags, back_populates="tags")

class Song(Base):
    __tablename__ = "songs"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)  # Original filename on computer
    display_name = Column(String, nullable=False)  # Display name in UI
    file_path = Column(String, nullable=False)  # Full path to file
    duration = Column(Float)  # Duration in seconds
    file_size = Column(Integer)  # File size in bytes
    
    # Audio analysis fields
    tempo = Column(Float)
    key = Column(String)
    mode = Column(String)  # major/minor
    energy = Column(Float, default=0.5)  # 0-1 scale
    valence = Column(Float, default=0.5)  # 0-1 scale (happiness)
    danceability = Column(Float, default=0.5)  # 0-1 scale
    
    # Metadata
    artist = Column(String)
    album = Column(String)
    year = Column(Integer)
    genre = Column(String)
    track_number = Column(Integer)  # Track number from metadata or filename
    
    created_at = Column(DateTime, default=datetime.utcnow)
    last_played = Column(DateTime)  # Track when song was last played
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    manually_added = Column(Boolean, default=False)

    tags = relationship("Tag", secondary=song_tags, back_populates="songs")

class ScannedDirectory(Base):
    __tablename__ = "scanned_directories"
    
    id = Column(Integer, primary_key=True, index=True)
    directory_path = Column(String, nullable=False, unique=True)
    recursive = Column(Boolean, default=True)
    last_scanned = Column(DateTime, default=datetime.utcnow)
    songs_found = Column(Integer, default=0)
    songs_added = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


# Unified Playlist System

# Association tables for UnifiedPlaylist
unified_playlist_manual_songs = Table(
    'unified_playlist_manual_songs',
    Base.metadata,
    Column('unified_playlist_id', Integer, ForeignKey('unified_playlists.id'), primary_key=True),
    Column('song_id', Integer, ForeignKey('songs.id'), primary_key=True),
    Column('order_index', Integer, default=0)
)

unified_playlist_criteria = Table(
    'unified_playlist_criteria',
    Base.metadata,
    Column('unified_playlist_id', Integer, ForeignKey('unified_playlists.id'), primary_key=True),
    Column('criteria_id', Integer, ForeignKey('dynamic_criteria.id'), primary_key=True),
    Column('order_index', Integer, default=0)
)

class UnifiedPlaylist(Base):
    __tablename__ = "unified_playlists"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    
    # Song ordering - JSON array of song IDs in display order
    # This allows for custom ordering of manual + dynamic songs
    song_order = Column(JSON, default=list)  # List of song IDs in order
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    manual_songs = relationship("Song", secondary=unified_playlist_manual_songs)
    dynamic_criteria = relationship("DynamicCriteria", secondary=unified_playlist_criteria)

class DynamicCriteria(Base):
    __tablename__ = "dynamic_criteria"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)  # Unique user-friendly name for this criteria
    
    # Flexible inclusion/exclusion criteria stored as JSON
    # Structure: {
    #   "include": {
    #     "tags": [tag_ids],
    #     "tag_groups": [group_ids],
    #     "artists": [artist_names],
    #     "albums": [album_names],
    #     "genres": [genre_names],
    #     "folders": [folder_names],
    #     "paths": [path_patterns],
    #     "energy": {"min": 0.0, "max": 1.0},
    #     "valence": {"min": 0.0, "max": 1.0},
    #     "danceability": {"min": 0.0, "max": 1.0},
    #     "tempo": {"min": 60, "max": 200},
    #     "duration": {"min": 30, "max": 600},
    #     "year": {"min": 1990, "max": 2024}
    #   },
    #   "exclude": {
    #     // Same structure as include
    #   }
    # }
    include_criteria = Column(JSON, default=dict)
    exclude_criteria = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
