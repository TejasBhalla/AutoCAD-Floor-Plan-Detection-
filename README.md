# Floor Plan Parser

AI-assisted floor plan parser that detects enclosed rooms from uploaded floor plan images using classical computer vision (OpenCV). Users can view, rename, reshape, add, and delete detected room polygons through an interactive canvas.

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Backend | Django 5, Django REST Framework, OpenCV, NumPy, Pillow |
| Frontend | React 18, Vite 5, Konva.js / React-Konva, Axios |

## Project Structure

```
FloorPlanTest/
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── floorplan/              # Django project config
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── api/                    # Django app — API + OpenCV logic
│   │   ├── __init__.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── opencv_service.py
│   └── media/                  # Uploaded images + saved layouts
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── index.css
│       ├── components/
│       │   ├── CanvasViewer.jsx
│       │   ├── RoomEditor.jsx
│       │   ├── Toolbar.jsx
│       │   └── UploadPanel.jsx
│       └── services/
│           └── api.js
└── venv/
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- npm

## Setup

### 1. Clone and enter the project

```bash
cd FloorPlanTest
```

### 2. Backend

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate    # macOS / Linux

pip install -r backend\requirements.txt
```

### 3. Frontend

```bash
cd frontend
npm install
cd ..
```

## Running

Open **two terminals** from the project root.

**Terminal 1 — Django backend** (port 8000):

```bash
venv\Scripts\activate
cd backend
python manage.py runserver
```

**Terminal 2 — Vite dev server** (port 3000):

```bash
cd frontend
npm run dev
```

Open **http://localhost:3000** in your browser.

The Vite dev server proxies `/api` and `/media` requests to Django on port 8000, so no CORS issues in development.

## API Endpoints

### Upload and process a floor plan

```
POST /api/upload-floorplan/
Content-Type: multipart/form-data
```

| Field | Type | Description |
|-------|------|-------------|
| `image` | File | PNG or JPG floor plan image |

**Response (200):**

```json
{
  "image_width": 1200,
  "image_height": 900,
  "image_url": "/media/floorplans/latest_floorplan.png",
  "rooms": [
    {
      "id": 1,
      "name": "Room 1",
      "polygon": [[120, 80], [420, 80], [420, 300], [120, 300]]
    }
  ]
}
```

### Save layout

```
POST /api/save-layout/
Content-Type: application/json
```

**Request body:**

```json
{
  "rooms": [
    {
      "id": 1,
      "name": "Living Room",
      "polygon": [[120, 80], [420, 80], [420, 300], [120, 300]]
    }
  ]
}
```

Saves to `backend/media/layouts/saved_layout.json`.

### Load layout

```
GET /api/load-layout/
```

Returns the previously saved layout JSON, or 404 if none exists.

## OpenCV Processing Pipeline

The room detection uses a classical computer vision pipeline with hierarchical contour analysis:

```
Input Image
    │
    ▼
Grayscale Conversion
    │
    ▼
Gaussian Blur (5x5)          — reduces noise
    │
    ▼
Adaptive Threshold            — binary image: walls=white, rooms=black
    │
    ▼
Morphological Close (5x5)    — bridges small gaps in walls
    │
    ▼
findContours(RETR_TREE)      — all contours + parent/child hierarchy
    │
    ▼
Hierarchy Filtering           — rooms = direct children of the floor boundary
    │
    ▼
Polygon Approximation         — cv2.approxPolyDP reduces vertex count
    │
    ▼
JSON Response                 — polygon coordinates for each room
```

Key details:

- `RETR_TREE` returns every contour with a hierarchy array (`[next, prev, child, parent]`)
- The largest top-level contour (no parent) is identified as the floor boundary
- Only direct children of the floor boundary are treated as rooms
- Contours smaller than 0.1% of total image area are discarded as noise

## Frontend Features

| Feature | Description |
|---------|-------------|
| Upload | Drag-and-drop or file picker for PNG/JPG images |
| Polygon overlay | Detected rooms shown as semi-transparent blue polygons with black borders |
| Click to select | Click a polygon to highlight it and open the editor panel |
| Rename rooms | Edit the room name in the sidebar — changes apply on blur or Enter |
| Drag vertices | Grab any vertex handle to reshape the polygon in real-time |
| Zoom | Mouse wheel zoom in/out, or use toolbar buttons |
| Pan | Shift+click drag or middle-click drag to pan the canvas |
| Add room | Click "Add Room" to insert a default rectangular polygon at the center |
| Delete room | Delete via the sidebar button or the room list |
| Save | Persists the current layout to the backend JSON file |
| Room count | Header displays the total number of detected/active rooms |

## File Overview

### Backend

| File | Purpose |
|------|---------|
| `floorplan/settings.py` | Django settings — apps, middleware, media config |
| `floorplan/urls.py` | Root URL router — mounts `api/` endpoints |
| `api/views.py` | DRF views for upload, save, and load |
| `api/opencv_service.py` | OpenCV pipeline — all image processing logic |
| `api/urls.py` | API URL routes |

### Frontend

| File | Purpose |
|------|---------|
| `src/App.jsx` | Root component — state management, orchestrates all panels |
| `src/components/UploadPanel.jsx` | Drag-and-drop upload with loading state |
| `src/components/CanvasViewer.jsx` | Konva stage — image display, polygon rendering, vertex dragging, zoom/pan |
| `src/components/RoomEditor.jsx` | Sidebar — room list, name editor, delete, save |
| `src/components/Toolbar.jsx` | Zoom controls and add-room button |
| `src/services/api.js` | Axios client for all backend API calls |
| `vite.config.js` | Vite config with proxy rules for `/api` and `/media` |

## Configuration

### Django settings (`backend/floorplan/settings.py`)

| Setting | Value | Notes |
|---------|-------|-------|
| `DEBUG` | `True` | Set to `False` in production |
| `ALLOWED_HOSTS` | `['*']` | Restrict in production |
| `MEDIA_ROOT` | `backend/media/` | Where uploads and layouts are saved |
| `CORS_ALLOW_ALL_ORIGINS` | `True` | Set to `False` and configure allowed origins in production |

### Vite proxy (`frontend/vite.config.js`)

| Path | Proxied to |
|------|-----------|
| `/api/*` | `http://localhost:8000` |
| `/media/*` | `http://localhost:8000` |

## License

This is a proof-of-concept project. No license specified.
