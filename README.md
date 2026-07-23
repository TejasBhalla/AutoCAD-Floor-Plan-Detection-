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

## OpenCV Service (`backend/api/opencv_service.py`)

The room detection engine is a pure classical computer vision pipeline — no ML models required. It uses rotated-kernel morphological wall extraction and connected-component analysis to identify enclosed rooms from floor plan images.

### Supported Input Formats

| Format | Handling |
|--------|----------|
| PNG / JPG | Decoded directly via `cv2.imdecode` |
| SVG | Detected by checking the first 1000 bytes for `<svg`/`<SVG` tags, then rasterized to PNG via `resvg_py.svg_to_bytes` at 2200 px width before processing |

### Configuration (`ParserConfig`)

All tunable parameters live in the `ParserConfig` dataclass. A `DEFAULT_CONFIG` instance is used throughout the pipeline.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_processing_size` | `2200` | Longest edge after resize — keeps processing fast on large plans |
| `adaptive_block_size` | `25` | Block size for adaptive threshold (must be odd) |
| `adaptive_c` | `5` | Constant subtracted from adaptive threshold mean |
| `gaussian_kernel` | `5` | Gaussian blur kernel size (must be odd) |
| `wall_kernel` | `7` | Structural element size for gap bridging |
| `bridge_iterations` | `3` | Morph-close iterations for wall bridging |
| `min_component_area` | `120` | Minimum blob area (px) kept after initial cleanup |
| `min_room_area` | `800` | Minimum area for a connected component to be a room |
| `max_room_area_ratio` | `0.90` | Components larger than 90% of total image area are rejected |
| `polygon_epsilon` | `0.002` | `approxPolyDP` simplification factor (fraction of perimeter) |
| `remove_text` | `True` | Flag for text removal (reserved for future use) |
| `debug` | `False` | When `True`, shows intermediate images via `cv2.imshow` |

### Processing Pipeline

```
Input Image (bytes)
    │
    ▼
load_image()                    — auto-detect SVG vs raster, decode to BGR numpy array
    │
    ▼
resize_for_processing()         — scale longest edge to ≤ 2200 px (returns image + scale factor)
    │
    ▼
preprocess()
  ├─ cv2.cvtColor → grayscale
  ├─ cv2.GaussianBlur (5×5)
  └─ cv2.adaptiveThreshold (GAUSSIAN_C, BINARY_INV, block=25, C=5)
    │
    ▼
remove_small_components()       — cv2.connectedComponentsWithStats → drop blobs < 120 px
    │
    ▼
extract_walls()
  └─ For each angle in [0, 15, 30, …, 165]:
       ├─ _make_rotated_kernel(45, angle)
       │    └─ draw 45-px line on canvas → cv2.getRotationMatrix2D → cv2.warpAffine (INTER_NEAREST)
       ├─ cv2.morphologyEx(MORPH_OPEN, kernel)
       └─ cv2.bitwise_or into accumulator
    │
    ▼
bridge_wall_gaps()              — cv2.morphologyEx(MORPH_CLOSE, 7×7 rect, iterations=3)
    │
    ▼
thicken_walls()                 — cv2.dilate(5×5 rect, iterations=2)
    │
    ▼
compute_free_space()            — cv2.bitwise_not (white = walkable, black = walls)
    │
    ▼
remove_outside_region()         — cv2.floodFill from (0,0) with seed=0 → erases exterior
    │
    ▼
remove_thin_structures()        — cv2.morphologyEx(MORPH_OPEN, 2×2 rect) → removes slivers
    │
    ▼
detect_room_components()        — cv2.connectedComponentsWithStats (connectivity=8)
    │                              filter by min_room_area (800) and max_room_area_ratio (0.90)
    ▼
filter_rooms()                  — reject rooms by aspect ratio and fill ratio:
    │                              corridor-like (aspect > 8 or < 0.12): fill_ratio < 0.5 → reject
    │                              normal rooms: fill_ratio < 0.25 → reject
    ▼
extract_room_polygons()         — per room:
    ├─ largest_contour()        — cv2.findContours(RETR_EXTERNAL, CHAIN_APPROX_NONE) → pick largest
    ├─ contour_to_polygon()     — cv2.approxPolyDP (epsilon = 0.002 × perimeter)
    ├─ clean_polygon()          — remove consecutive duplicate vertices + closing duplicate
    ├─ scale_polygon()          — map coordinates back to original image scale
    └─ attach centroid, bbox, area
    │
    ▼
Returns { image_width, image_height, room_count, rooms[] }
```

### Key Functions

#### Image Loading

- **`load_image(image_bytes)`** — Inspects the first 1000 bytes for SVG markers. SVGs are rasterized via `resvg_py`; rasters are decoded with `cv2.imdecode`. Raises `ValueError` on failure.
- **`svg_to_image(svg_bytes, output_width=2200)`** — Renders SVG to PNG bytes at the target width, then decodes to a BGR numpy array.
- **`resize_for_processing(image, max_size)`** — Scales the longest edge to `max_size` using `cv2.INTER_AREA`. Returns the resized image and the scale factor (1.0 if no resize needed).

#### Preprocessing

- **`preprocess(image, config)`** — Grayscale → Gaussian blur → adaptive threshold. Produces a clean binary image where wall/line pixels are white (255).
- **`odd(value)`** — Ensures a kernel size is odd and ≥ 3.

#### Wall Extraction

- **`extract_walls(binary)`** — The core innovation. Creates a 45-pixel horizontal line kernel, embeds it in a square canvas, and rotates it to 12 angles (0° through 165° in 15° steps) using `cv2.getRotationMatrix2D` + `cv2.warpAffine` with `INTER_NEAREST`. Each rotated kernel is applied via morphological opening, and results are OR'd together. This captures walls at any orientation — horizontal, vertical, and diagonal — which orthogonal-only morphology would miss.
- **`_make_rotated_kernel(length, angle)`** — Builds a single rotated line kernel. Draws a horizontal line on a zero canvas, rotates by the given angle, and returns the result.

#### Wall Cleanup

- **`bridge_wall_gaps(walls, config)`** — Morphological closing with a 7×7 rectangular kernel, 3 iterations. Reconnects small breaks in wall segments caused by the opening step.
- **`thicken_walls(walls)`** — Dilation with a 5×5 rectangular kernel, 2 iterations. Ensures walls are thick enough to act as barriers for flood fill.

#### Room Detection

- **`compute_free_space(walls)`** — Simple bitwise invert. White pixels become walkable/room space; black pixels become walls.
- **`remove_outside_region(free_space)`** — Flood fill starting from pixel (0,0). Fills the connected exterior region with black, leaving only enclosed rooms white.
- **`remove_thin_structures(binary)`** — Morphological opening with a 2×2 kernel. Removes thin slivers and noise left over from earlier steps.
- **`detect_room_components(free_space, config)`** — Labels connected components (8-connectivity) via `cv2.connectedComponentsWithStats`. Filters by absolute area and maximum area ratio. Returns a list of dicts with `id`, `bbox`, `area`, and `mask`.
- **`filter_rooms(rooms, config)`** — Applies geometric heuristics:
  - **Corridor-like** (aspect ratio > 8 or < 0.12): rejected if fill ratio < 0.5
  - **Normal rooms**: rejected if fill ratio < 0.25

#### Polygon Extraction

- **`largest_contour(mask)`** — Finds external contours and returns the one with the largest area.
- **`contour_to_polygon(contour, config)`** — Simplifies a contour to a polygon using `cv2.approxPolyDP` with epsilon = 0.002 × perimeter. Returns a list of `[x, y]` integer pairs.
- **`clean_polygon(points)`** — Removes consecutive duplicate vertices and the closing duplicate (if first == last).
- **`scale_polygon(polygon, scale)`** — Maps polygon coordinates back to the original image resolution by dividing by the scale factor.
- **`extract_room_polygons(rooms, scale, config)`** — Orchestrates the full extraction: for each room, finds the largest contour, simplifies it, cleans it, scales it, and computes centroid/bbox/area. Returns the final room list.

#### Geometry Helpers

| Function | Description |
|----------|-------------|
| `contour_centroid(contour)` | Computes centroid via `cv2.moments`, falls back to bounding rect center |
| `contour_bbox(contour)` | Returns `(x, y, w, h)` via `cv2.boundingRect` |
| `polygon_area(contour)` | Returns area via `cv2.contourArea` |

#### Debug & Visualization

- **`show(title, image, config)`** — Displays an image in a window when `config.debug` is `True`. No-op otherwise.
- **`draw_rooms_on_image(image_bytes, rooms)`** — Draws filled semi-transparent colored overlays, black polygon outlines, red centroid dots, and room name labels on a copy of the original image. Returns JPEG-encoded bytes.
- **`room_statistics(rooms)`** — Returns `count`, `average_area`, and `largest_area` for a list of rooms.

#### Main Entry Point

- **`process_floorplan(image_bytes, config=DEFAULT_CONFIG)`** — The top-level function called by the Django view. Runs the full pipeline (load → resize → preprocess → segment → extract polygons) and returns:
  ```json
  {
    "image_width": 1200,
    "image_height": 900,
    "room_count": 5,
    "rooms": [
      {
        "id": 1,
        "name": "Room 1",
        "polygon": [[120, 80], [420, 80], [420, 300], [120, 300]],
        "centroid": [270, 190],
        "bbox": [120, 80, 300, 220],
        "area": 52800
      }
    ]
  }
  ```

### Design Rationale

- **No ML dependency**: The entire pipeline is classical CV — no model files, no GPU, no training data. This makes deployment simple and reproducible.
- **Rotated kernel bank**: Floor plans often contain walls at non-orthogonal angles (e.g., angled rooms, bay windows). A 12-angle kernel bank at 15° intervals covers all practical wall orientations while keeping processing fast.
- **Flood fill exterior removal**: By inverting the wall image and flood-filling from the image corner, we cleanly separate interior rooms from the background without needing to detect the building outline explicitly.
- **Two-pass filtering**: First by absolute area (removes tiny artifacts), then by geometric shape (aspect ratio + fill ratio) to reject corridor-like fragments and sparse noise that survived the morphological steps.

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
