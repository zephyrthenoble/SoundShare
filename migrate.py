#!/usr/bin/env python3
"""
Migration wrapper script for SoundShare

This script provides a convenient way to run migration commands from the project root.
All commands are forwarded to the actual migration utility in the migrations folder.

Usage:
    python migrate.py <command> [args...]
    
Examples:
    python migrate.py create "Add user table"
    python migrate.py upgrade
    python migrate.py current
    python migrate.py help
"""

import sys
import subprocess
from pathlib import Path

def main():
    """Forward all arguments to the actual migration script."""
    # Path to the actual migration script
    migrations_script = Path(__file__).parent / "migrations" / "migrations.py"
    
    if not migrations_script.exists():
        print("Error: Migration script not found at", migrations_script)
        return 1
    
    # Forward all arguments to the migration script
    cmd = ["uv", "run", "python", str(migrations_script)] + sys.argv[1:]
    
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except KeyboardInterrupt:
        print("\nMigration cancelled.")
        return 1
    except Exception as e:
        print(f"Error running migration command: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
