import os
from pathlib import Path
from functools import lru_cache

@lru_cache(maxsize=1)
def get_database_url() -> str:
    """Get database URL from environment variable."""
    raw_path = os.environ.get('SOUNDSHARE_DB_PATH', 'soundshare.db')
    # If raw_path contains :// treat as full URL
    if '://' in raw_path:
        return raw_path
    # Make absolute path
    root = Path(__file__).resolve().parents[2]
    db_path = (root / raw_path).resolve()
    # Use absolute path for consistency (works regardless of cwd)
    return f'sqlite:///{db_path}'

@lru_cache(maxsize=1)
def get_library_path() -> Path:
    """Get and validate the library path from environment variables."""
    raw_path = os.environ.get('SOUNDSHARE_LIBRARY_PATH', '')
    
    if not raw_path:
        raise ValueError("SOUNDSHARE_LIBRARY_PATH environment variable not set")
    
    path = Path(raw_path).resolve()
    
    # Security validation: ensure path is absolute and exists
    if not path.is_absolute():
        raise ValueError("SOUNDSHARE_LIBRARY_PATH must be an absolute path")
    
    if not path.exists():
        raise ValueError(f"SOUNDSHARE_LIBRARY_PATH does not exist: {path}")
        
    if not path.is_dir():
        raise ValueError(f"SOUNDSHARE_LIBRARY_PATH is not a directory: {path}")
    
    return path
