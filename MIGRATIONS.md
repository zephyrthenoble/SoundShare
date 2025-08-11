# Database Migrations Guide

This document explains how to manage database schema changes in SoundShare using Alembic migrations.

## Overview

SoundShare uses [Alembic](https://alembic.sqlalchemy.org/) for database migrations. Alembic provides a systematic way to manage database schema changes over time, allowing you to:

- Track all database changes with version control
- Upgrade/downgrade database schemas safely
- Share schema changes across different environments
- Maintain data integrity during schema modifications

## Quick Start

### Creating a New Migration

```bash
# Create a migration with autogenerate (recommended for most cases)
python migrate.py create "Add user preferences table"

# This will generate a migration file with detected changes
```

### Applying Migrations

```bash
# Upgrade to the latest version
python migrate.py upgrade

# Upgrade to a specific revision
python migrate.py upgrade abc123

# Downgrade to previous version
python migrate.py downgrade -1

# Downgrade to specific revision
python migrate.py downgrade abc123
```

### Checking Migration Status

```bash
# Show current database revision
python migrate.py current

# Show migration history
python migrate.py history
```

## Migration Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `create` | Create a new migration | `python migrate.py create "Add indexes"` |
| `upgrade` | Apply migrations to upgrade database | `python migrate.py upgrade` |
| `downgrade` | Revert migrations to downgrade database | `python migrate.py downgrade -1` |
| `current` | Show current database revision | `python migrate.py current` |
| `history` | Show all migration history | `python migrate.py history` |
| `reset` | Reset database (⚠️ DESTROYS ALL DATA) | `python migrate.py reset` |
| `help` | Show help information | `python migrate.py help` |

## Best Practices

### 1. **Always Review Generated Migrations**

Autogenerate is powerful but not perfect. Always review the generated migration file before applying:

```python
# Check the generated file in alembic/versions/
# Ensure the upgrade() and downgrade() functions are correct
```

### 2. **Use Descriptive Migration Names**

```bash
# Good ✅
python migrate.py create "Add last_played timestamp to songs table"
python migrate.py create "Create user_preferences table with settings"

# Avoid ❌
python migrate.py create "fix stuff"
python migrate.py create "update"
```

### 3. **Test Migrations Both Ways**

```bash
# Test upgrade
python migrate.py upgrade

# Test downgrade
python migrate.py downgrade -1

# Re-upgrade to verify round-trip
python migrate.py upgrade
```

### 4. **Backup Before Major Changes**

For production databases, always backup before applying migrations:

```bash
# Backup database
cp soundshare.db soundshare.db.backup.$(date +%Y%m%d_%H%M%S)

# Then apply migration
python migrate.py upgrade
```

## Manual Migrations

Some changes require manual migration files (e.g., data migrations, complex schema changes):

```bash
# Create empty migration template
uv run alembic revision -m "Manual data migration"
```

Then edit the generated file:

```python
def upgrade() -> None:
    """Upgrade schema."""
    # Add your custom migration logic here
    op.execute("UPDATE songs SET status = 'active' WHERE status IS NULL")

def downgrade() -> None:
    """Downgrade schema."""
    # Add reverse logic
    op.execute("UPDATE songs SET status = NULL WHERE status = 'active'")
```

## SQLite Limitations

SQLite has limited ALTER TABLE support. Some operations require workarounds:

### ✅ Supported Operations
- Add column: `op.add_column('table', sa.Column('name', sa.String()))`
- Drop column: `op.drop_column('table', 'column_name')`
- Create/drop tables: `op.create_table()` / `op.drop_table()`
- Create/drop indexes: `op.create_index()` / `op.drop_index()`

### ❌ Unsupported Operations
- Alter column type
- Rename columns
- Add constraints to existing columns

For unsupported operations, use the "create new table and migrate data" pattern:

```python
def upgrade():
    # Create new table with desired schema
    op.create_table('songs_new', ...)
    
    # Copy data
    op.execute("INSERT INTO songs_new SELECT ... FROM songs")
    
    # Drop old table and rename
    op.drop_table('songs')
    op.rename_table('songs_new', 'songs')
```

## Troubleshooting

### Migration Fails with "Target database is not up to date"

```bash
# Check current status
python migrate.py current

# If behind, upgrade first
python migrate.py upgrade

# Then create new migration
python migrate.py create "description"
```

### Migration Fails with SQL Errors

1. Check the generated migration file for syntax errors
2. Test the SQL manually in SQLite browser
3. Consider creating a manual migration for complex changes

### Need to Undo Last Migration

```bash
# Downgrade one step
python migrate.py downgrade -1

# Or remove the migration file and re-create
rm migrations/versions/problematic_migration.py
python migrate.py create "corrected description"
```

### Database Schema Drift

If your database schema doesn't match the models:

```bash
# Generate migration to sync
python migrate.py create "Sync database with models"

# Review and apply
python migrate.py upgrade
```

## Production Deployment

### 1. **Version Control**
- Always commit migration files to version control
- Include migrations in deployment scripts

### 2. **Automated Deployment**
```bash
# In deployment script
python migrate.py current  # Check status
python migrate.py upgrade  # Apply pending migrations
```

### 3. **Zero-Downtime Migrations**
- Add columns as nullable first
- Populate data in separate migration
- Add constraints in final migration

### 4. **Rollback Strategy**
- Test downgrade migrations thoroughly
- Have data backups ready
- Document rollback procedures

## File Structure

```
soundshare/
├── migrations/                 # Migration system directory
│   ├── alembic.ini            # Alembic configuration
│   ├── env.py                 # Environment configuration
│   ├── migrations.py          # Migration utility script
│   ├── script.py.mako         # Migration template
│   └── versions/              # Migration files
│       ├── abc123_initial.py
│       └── def456_add_field.py
├── migrate.py                 # Convenient wrapper script
└── database/
    └── models.py              # SQLAlchemy models
```

## Examples

### Adding a New Column

```bash
# 1. Add field to model in database/models.py
class Song(Base):
    # ... existing fields ...
    play_count = Column(Integer, default=0)

# 2. Create migration
python migrate.py create "Add play_count to songs"

# 3. Review generated migration file
# 4. Apply migration
python migrate.py upgrade
```

### Creating a New Table

```bash
# 1. Add model class in database/models.py
class UserPreferences(Base):
    __tablename__ = "user_preferences"
    id = Column(Integer, primary_key=True)
    # ... other fields ...

# 2. Create migration
python migrate.py create "Add user_preferences table"

# 3. Apply migration
python migrate.py upgrade
```

### Data Migration

```bash
# 1. Create manual migration
uv run alembic revision -m "Migrate legacy data format"

# 2. Edit migration file
def upgrade():
    op.execute("""
        UPDATE songs 
        SET normalized_title = LOWER(TRIM(title))
        WHERE normalized_title IS NULL
    """)
```

## Getting Help

```bash
# Show available commands
python migrate.py help

# Show Alembic help
uv run alembic --help

# Check current database status
python migrate.py current
```

For more information, see the [Alembic documentation](https://alembic.sqlalchemy.org/).
