from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Table, Text, DateTime
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

playlist_songs = Table(
    'playlist_songs',
    Base.metadata,
    Column('playlist_id', Integer, ForeignKey('playlists.id'), primary_key=True),
    Column('song_id', Integer, ForeignKey('songs.id'), primary_key=True),
    Column('order_index', Integer, default=0)
)

dynamic_playlist_include_tags = Table(
    'dynamic_playlist_include_tags',
    Base.metadata,
    Column('dynamic_playlist_id', Integer, ForeignKey('dynamic_playlists.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)

dynamic_playlist_exclude_tags = Table(
    'dynamic_playlist_exclude_tags',
    Base.metadata,
    Column('dynamic_playlist_id', Integer, ForeignKey('dynamic_playlists.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)

dynamic_playlist_include_groups = Table(
    'dynamic_playlist_include_groups',
    Base.metadata,
    Column('dynamic_playlist_id', Integer, ForeignKey('dynamic_playlists.id'), primary_key=True),
    Column('group_id', Integer, ForeignKey('tag_groups.id'), primary_key=True)
)

dynamic_playlist_exclude_groups = Table(
    'dynamic_playlist_exclude_groups',
    Base.metadata,
    Column('dynamic_playlist_id', Integer, ForeignKey('dynamic_playlists.id'), primary_key=True),
    Column('group_id', Integer, ForeignKey('tag_groups.id'), primary_key=True)
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

class Playlist(Base):
    __tablename__ = "playlists"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    songs = relationship("Song", secondary=playlist_songs)

class DynamicPlaylist(Base):
    __tablename__ = "dynamic_playlists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    
    # Audio feature filters
    energy_min = Column(Float)  # Minimum energy level (0.0-1.0)
    energy_max = Column(Float)  # Maximum energy level (0.0-1.0)
    valence_min = Column(Float)  # Minimum valence/mood (0.0-1.0)
    valence_max = Column(Float)  # Maximum valence/mood (0.0-1.0)
    danceability_min = Column(Float)  # Minimum danceability (0.0-1.0)
    danceability_max = Column(Float)  # Maximum danceability (0.0-1.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    include_tags = relationship("Tag", secondary=dynamic_playlist_include_tags)
    exclude_tags = relationship("Tag", secondary=dynamic_playlist_exclude_tags)
    include_groups = relationship("TagGroup", secondary=dynamic_playlist_include_groups)
    exclude_groups = relationship("TagGroup", secondary=dynamic_playlist_exclude_groups)
