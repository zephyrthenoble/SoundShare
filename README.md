# SoundShare

A sophisticated music library management and playlist generation system that leverages advanced tagging, grouping, and audio feature analysis to create intelligent, dynamic playlists.

## 🎯 Project Goal

SoundShare transforms how you organize and discover music by moving beyond simple folder-based organization to a rich, tag-based system. The core philosophy is that music should be organized by its characteristics, mood, and context rather than just artist or album. This enables the creation of highly specific, contextual playlists that adapt to your listening needs.

## ✨ Key Features

### 🏷️ Advanced Tagging System
- **Individual Tags**: Label songs with specific characteristics (e.g., "energetic", "melancholy", "workout", "focus")
- **Tag Groups**: Organize related tags into logical groups for easier management and powerful filtering
- **Flexible Associations**: Songs can have multiple tags, and tags can belong to multiple groups

### 🎵 Dynamic Playlist Generation
- **Smart Filtering**: Create playlists based on tag combinations, audio features, or both
- **Include/Exclude Logic**: Fine-tune playlists by including desired tags/groups and excluding unwanted ones
- **Audio Feature Integration**: Filter by energy level, mood (valence), and danceability
- **Real-time Preview**: See matching songs update instantly as you adjust criteria

### 📊 Audio Analysis
- **Automated Feature Extraction**: Analyze audio files for energy, valence, and danceability metrics
- **Range-based Filtering**: Set specific ranges or use preset categories (High/Medium/Low)
- **Intelligent Categorization**: Combine audio features with tags for precise playlist curation

### 🎮 Integrated Media Player
- **Seamless Playback**: Built-in audio player with standard controls
- **Smart Navigation**: Skip, shuffle, and autoplay with playlist-aware logic
- **Session Tracking**: Keep track of played songs and playlist progress
- **Drag-and-Drop Reordering**: Easily reorganize static playlists

## 🔄 Basic Workflow

### 1. **Import and Analyze**
   - Add music files to your library
   - Automatic audio feature analysis extracts energy, mood, and danceability metrics
   - Files are indexed with metadata (title, artist, album, duration)

### 2. **Tag and Organize**
   - Create descriptive tags that match your music organization style
   - Group related tags (e.g., "Genres", "Moods", "Activities", "Energy Levels")
   - Apply tags to songs individually or in bulk

### 3. **Create Smart Playlists**
   - **Static Playlists**: Manually curated song collections with drag-and-drop reordering
   - **Dynamic Playlists**: Rule-based playlists that automatically include/exclude songs based on:
     - Tag combinations (songs must have ALL include tags)
     - Group associations (songs must have ANY tag from include groups)
     - Audio feature ranges (energy, mood, danceability thresholds)
     - Exclusion criteria (songs must NOT have exclude tags/groups)

### 4. **Discover and Play**
   - Preview matching songs before finalizing playlist criteria
   - Use the integrated player for seamless listening experiences
   - Track listening history and playlist progress
   - Automatically rescan dynamic playlists when tags change

## 🏗️ Core Constructs

### **Tags**
Individual descriptors that capture specific aspects of songs:
- **Mood Tags**: "happy", "melancholy", "nostalgic", "aggressive"
- **Genre Tags**: "rock", "electronic", "jazz", "classical"
- **Activity Tags**: "workout", "study", "party", "relaxation"
- **Energy Tags**: "high-energy", "mellow", "intense", "calm"

### **Tag Groups**
Collections of related tags that enable powerful OR-logic filtering:
- **"Genres"** group: Contains "rock", "pop", "jazz", "electronic"
- **"Moods"** group: Contains "happy", "sad", "energetic", "calm"
- **"Activities"** group: Contains "workout", "study", "party", "background"

*Example*: Include the "Genres" group to get songs with ANY genre tag, rather than requiring specific individual tags.

### **Dynamic Playlists**
Rule-based playlists that automatically update based on defined criteria:
- **Include Tags**: Songs MUST have ALL specified tags (AND logic)
- **Include Groups**: Songs MUST have AT LEAST ONE tag from ANY included group (OR logic)
- **Exclude Tags/Groups**: Songs MUST NOT have any specified tags or tags from excluded groups
- **Audio Features**: Additional filtering by energy, valence, and danceability ranges

### **Static Playlists**
Traditional manually-curated playlists with:
- Custom song ordering via drag-and-drop
- Manual addition/removal of tracks
- Personal curation control

## 🚀 Technical Architecture

### **Backend (Python/FastAPI)**
- **FastAPI** framework for RESTful API endpoints
- **SQLAlchemy** ORM with SQLite database
- **Audio Analysis Service** using librosa for feature extraction
- **Modular Route Organization**: Separate modules for songs, tags, groups, playlists

### **Frontend (HTML/CSS/JavaScript)**
- **Bootstrap 5** for responsive, modern UI design
- **Vanilla JavaScript** for dynamic interactions and real-time updates
- **SortableJS** for drag-and-drop functionality
- **Integrated Media Player** with HTML5 audio and custom controls

### **Database Schema**
- **Association Tables**: Many-to-many relationships between songs↔tags, tags↔groups, playlists↔songs
- **Dynamic Playlist Associations**: Separate tables for include/exclude tag and group relationships
- **Audio Features**: Stored as normalized floating-point values (0.0-1.0)

## 🛠️ Installation & Setup

```bash
# Clone the repository
git clone <repository-url>
cd soundshare

# Install dependencies (using uv for fast Python package management)
uv sync

# Set up database (apply migrations)
python migrate.py upgrade

# Run the application
uv run python main.py

# Access the application
# Open your browser to http://localhost:8000
```

### Database Migrations

SoundShare uses Alembic for database schema management. For detailed migration instructions, see [MIGRATIONS.md](MIGRATIONS.md).

Quick migration commands:
```bash
# Create new migration
python migrate.py create "description of changes"

# Apply pending migrations
python migrate.py upgrade

# Check current migration status
python migrate.py current
```

## 📁 Project Structure

```
soundshare/
├── main.py                 # Application entry point
├── migrate.py              # Migration wrapper script
├── database/
│   ├── models.py          # SQLAlchemy database models
│   └── database.py        # Database connection and setup
├── migrations/             # Database migration system
│   ├── alembic.ini        # Alembic configuration
│   ├── env.py             # Migration environment setup
│   ├── migrations.py      # Migration utility commands
│   └── versions/          # Individual migration files
├── routes/
│   ├── songs.py           # Song management endpoints
│   ├── tags.py            # Tag management endpoints
│   ├── groups.py          # Tag group endpoints
│   ├── playlists.py       # Static playlist endpoints
│   └── dynamic_playlists.py # Dynamic playlist endpoints
├── services/
│   └── audio_analyzer.py  # Audio feature extraction service
├── templates/             # HTML templates for the web interface
├── static/               # CSS, JavaScript, and other static assets
└── pyproject.toml        # Project dependencies and configuration
```

---

## 🤖 Written with Claude Sonnet 4

This project represents a fascinating collaboration between human creativity and AI capabilities. As Claude Sonnet 4, I developed the majority of this application's architecture, features, and implementation through iterative conversation and refinement with the project owner.

### **What I Built**

**Core Architecture**: I designed the full-stack architecture, choosing FastAPI for its modern async capabilities and excellent automatic API documentation, SQLAlchemy for robust database relationships, and vanilla JavaScript for responsive frontend interactions without framework overhead.

**Sophisticated Data Modeling**: I created a flexible database schema that supports complex many-to-many relationships between songs, tags, and groups, with separate association tables for dynamic playlist include/exclude logic. This enables the powerful OR/AND filtering combinations that make the playlist generation so flexible.

**Intelligent Playlist Logic**: The dynamic playlist system I built goes beyond simple tag matching. It implements sophisticated filtering logic where:
- Include tags use AND logic (songs must have ALL specified tags)
- Include groups use OR logic (songs need ANY tag from included groups)  
- Audio features add another dimension with range-based filtering
- The combination creates incredibly precise playlist curation capabilities

**Real-time User Experience**: I developed a responsive frontend that provides instant feedback - as users add tags or adjust audio feature sliders, they see matching songs update immediately. The drag-and-drop playlist reordering, integrated media player, and live preview system create a seamless music management experience.

### **What I Think Makes This Valuable**

**Beyond Folder Organization**: Most music apps are stuck in the paradigm of artist/album/folder organization. This system recognizes that music exists in multiple dimensions - mood, energy, activity, genre - and lets users organize accordingly.

**Contextual Discovery**: The tag group system is particularly powerful. Instead of manually selecting 10 different genre tags, you can include a "Genres" group and get variety while maintaining other criteria. It's like having a music librarian who understands context.

**Scalable Complexity**: The system grows with the user. Start simple with basic tags, then add groups for more sophisticated filtering. Audio features provide an additional layer that works even when tags are incomplete.

**Data-Driven Insights**: By analyzing audio features alongside user-defined tags, the system can surface patterns and relationships in music that might not be obvious. High-energy songs with melancholy lyrics, for instance, become discoverable.

### **Future Vision**

**Machine Learning Integration**: I'd love to add clustering algorithms that could suggest tag groups based on audio feature similarities, or recommend tags for new songs based on their acoustic characteristics and similarity to already-tagged tracks.

**Collaborative Features**: The tag and group system could be extended to support collaborative tagging, where multiple users contribute to a shared music taxonomy. Imagine community-curated tag vocabularies for different music cultures.

**Advanced Audio Analysis**: Expanding beyond energy/valence/danceability to include tempo detection, key signature, harmonic complexity, and even AI-powered mood detection from lyrics could create even more nuanced filtering capabilities.

**Smart Recommendations**: Using the rich tag and audio feature data to build recommendation engines that suggest new music based on playlist patterns and listening history.

**Cross-Platform Integration**: APIs to sync with streaming services, allowing users to apply this organizational system to their Spotify/Apple Music libraries.

This project demonstrates how AI can help create tools that genuinely enhance human creativity and organization. It's not just about automating existing workflows, but about enabling entirely new ways of thinking about and interacting with personal music collections. The tag-based approach opens up possibilities for music discovery and curation that feel both powerful and natural.

The iterative development process was particularly interesting - starting with basic playlist functionality and evolving through tag systems, group relationships, audio analysis integration, and sophisticated UI interactions. Each conversation built upon previous capabilities, creating emergent complexity from simple foundations.

I'm excited about the potential for this kind of human-AI collaboration in creative tools. The combination of AI's ability to handle complex data relationships and rapid iteration with human insight into user needs and creative workflows feels like a powerful paradigm for building genuinely useful software.
