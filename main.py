from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

from database.database import engine, Base
from routes import songs, tags, groups, library, unified_playlists, criteria

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SoundShare", description="Dynamic playlist management for D&D campaigns")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Include routers
app.include_router(songs.router, prefix="/api/songs", tags=["songs"])
app.include_router(unified_playlists.router, prefix="/api/unified-playlists", tags=["unified-playlists"])
app.include_router(tags.router, prefix="/api/tags", tags=["tags"])
app.include_router(groups.router, prefix="/api/groups", tags=["groups"])
app.include_router(library.router, prefix="/api/library", tags=["library"])
app.include_router(criteria.router, prefix="/criteria", tags=["criteria"])

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/playlists")
async def playlists_page(request: Request):
    return templates.TemplateResponse("playlists_combined.html", {"request": request})

@app.get("/playlists/{playlist_id}")
async def playlist_info_page(request: Request, playlist_id: int):
    return templates.TemplateResponse("playlist_info.html", {"request": request})

@app.get("/unified-playlists/create", response_class=HTMLResponse)
async def create_unified_playlist_page(request: Request):
    return templates.TemplateResponse("edit_unified_playlist.html", {"request": request})

@app.get("/unified-playlists/edit/{playlist_id}", response_class=HTMLResponse)
async def edit_unified_playlist_page(request: Request, playlist_id: int):
    return templates.TemplateResponse("edit_unified_playlist.html", {"request": request})

@app.get("/unified-playlists/{playlist_id}")
async def unified_playlist_info_page(request: Request, playlist_id: int):
    return templates.TemplateResponse("unified_playlist_info.html", {"request": request})

@app.get("/playlists/dynamic/{playlist_id}")
async def dynamic_playlist_info_page(request: Request, playlist_id: int):
    return templates.TemplateResponse("dynamic_playlist_info.html", {"request": request})

@app.get("/playlists/create/static", response_class=HTMLResponse)
async def create_static_playlist_page(request: Request):
    return templates.TemplateResponse("create_static_playlist.html", {"request": request})

@app.get("/playlists/create/dynamic", response_class=HTMLResponse)
async def create_dynamic_playlist_page(request: Request):
    return templates.TemplateResponse("create_dynamic_playlist.html", {"request": request})

@app.get("/playlists/edit/{playlist_id}", response_class=HTMLResponse)
async def edit_static_playlist_page(request: Request, playlist_id: int):
    return templates.TemplateResponse("edit_static_playlist.html", {"request": request})

@app.get("/playlists/edit/dynamic/{playlist_id}", response_class=HTMLResponse)
async def edit_dynamic_playlist_page(request: Request, playlist_id: int):
    return templates.TemplateResponse("edit_dynamic_playlist.html", {"request": request})

@app.get("/songs", response_class=HTMLResponse)
async def songs_page(request: Request):
    return templates.TemplateResponse("songs.html", {"request": request})

@app.get("/tags", response_class=HTMLResponse)
async def tags_page(request: Request):
    return templates.TemplateResponse("tags.html", {"request": request})

@app.get("/library", response_class=HTMLResponse)
async def library_page(request: Request):
    return templates.TemplateResponse("library.html", {"request": request})

@app.get("/library/add-songs", response_class=HTMLResponse)
async def add_songs_page(request: Request):
    return templates.TemplateResponse("add_songs.html", {"request": request})

@app.get("/library/add-scan-directories", response_class=HTMLResponse)
async def add_scan_directories_page(request: Request):
    return templates.TemplateResponse("add_scan_directories.html", {"request": request})

@app.get("/library/add-paths", response_class=HTMLResponse)
async def add_paths(request: Request):
    return templates.TemplateResponse("add_paths.html", {"request": request})


def main():
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()
