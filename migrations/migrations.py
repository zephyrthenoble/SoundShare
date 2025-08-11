#!/usr/bin/env python3
"""
Database Migration Utility for SoundShare

This script provides convenient commands for managing database migrations
using Alembic. It wraps common Alembic commands with project-specific
configurations and provides helpful shortcuts.

Usage:
    python migrations.py create "migration description"
    python migrations.py upgrade
    python migrations.py downgrade
    python migrations.py current
    python migrations.py history
    python migrations.py reset
"""

import sys
import subprocess
import os
from pathlib import Path

def run_alembic_command(args):
    """Run an Alembic command using uv run."""
    cmd = ["uv", "run", "alembic"] + args
    original_dir = os.getcwd()  # Save current directory
    
    try:
        # Change to migrations directory to run alembic commands
        migrations_dir = Path(__file__).parent
        os.chdir(migrations_dir)
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(cmd)}")
        print(f"Exit code: {e.returncode}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        return False
    finally:
        # Always restore original directory
        os.chdir(original_dir)

def create_migration(description):
    """Create a new migration with autogenerate."""
    if not description:
        print("Error: Migration description is required")
        print("Usage: python migrations.py create \"description of changes\"")
        return False
    
    print(f"Creating new migration: {description}")
    return run_alembic_command(["revision", "--autogenerate", "-m", description])

def upgrade_database(target="head"):
    """Upgrade database to target revision (default: head)."""
    print(f"Upgrading database to {target}...")
    return run_alembic_command(["upgrade", target])

def downgrade_database(target):
    """Downgrade database to target revision."""
    if not target:
        print("Error: Target revision is required for downgrade")
        print("Usage: python migrations.py downgrade <revision>")
        print("       python migrations.py downgrade -1  # Go back one revision")
        return False
    
    print(f"Downgrading database to {target}...")
    return run_alembic_command(["downgrade", target])

def show_current():
    """Show current database revision."""
    print("Current database revision:")
    return run_alembic_command(["current", "-v"])

def show_history():
    """Show migration history."""
    print("Migration history:")
    return run_alembic_command(["history", "-v"])

def reset_database():
    """Reset database to base (WARNING: This will remove all data!)."""
    response = input("WARNING: This will reset the database and remove ALL data! Are you sure? (type 'yes' to confirm): ")
    if response.lower() != 'yes':
        print("Reset cancelled.")
        return False
    
    print("Resetting database...")
    # Remove the database file (it's in the parent directory)
    db_path = Path(__file__).parent.parent / "soundshare.db"
    if db_path.exists():
        db_path.unlink()
        print("Removed existing database file")
    
    # Run all migrations to recreate the database
    return upgrade_database()

def show_help():
    """Show help information."""
    print(__doc__)
    print("\nAvailable commands:")
    print("  create <description>    - Create a new migration")
    print("  upgrade [target]        - Upgrade to target revision (default: head)")
    print("  downgrade <target>      - Downgrade to target revision")
    print("  current                 - Show current revision")
    print("  history                 - Show migration history")
    print("  reset                   - Reset database (WARNING: removes all data)")
    print("  help                    - Show this help")
    print("\nExamples:")
    print("  python migrations.py create \"Add user preferences table\"")
    print("  python migrations.py upgrade")
    print("  python migrations.py downgrade -1")
    print("  python migrations.py current")

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        show_help()
        return 1
    
    command = sys.argv[1].lower()
    
    if command == "create":
        description = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        success = create_migration(description)
    elif command == "upgrade":
        target = sys.argv[2] if len(sys.argv) > 2 else "head"
        success = upgrade_database(target)
    elif command == "downgrade":
        target = sys.argv[2] if len(sys.argv) > 2 else ""
        success = downgrade_database(target)
    elif command == "current":
        success = show_current()
    elif command == "history":
        success = show_history()
    elif command == "reset":
        success = reset_database()
    elif command == "help":
        show_help()
        return 0
    else:
        print(f"Unknown command: {command}")
        show_help()
        return 1
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
