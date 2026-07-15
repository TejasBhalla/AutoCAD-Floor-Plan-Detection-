"""
OpenCV-based floor plan processing service.

Detects enclosed rooms by analyzing walls and contours in floor plan images.
Uses a classical computer vision pipeline — no AI/LLM APIs.

Tuned for large, complex floor plans containing many small rooms
(closets, bathrooms, storage), dense dimension/text annotations, and
double-line (thick) walls.
"""

import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunable defaults. Exposed as function args so callers can override per
# floor-plan type (e.g. hand-drawn vs. CAD export) without editing code.
# ---------------------------------------------------------------------------
DEFAULT_MAX_DIM_FOR_PROCESSING = 2000   # downscale larger images before contour work
DEFAULT_MIN_ROOM_AREA_PX = 250          # absolute floor, protects tiny real rooms
DEFAULT_MIN_ROOM_AREA_FRAC = 0.0004     # 0.04% of total area (lower than before)
DEFAULT_MAX_ROOM_AREA_FRAC = 0.85
DEFAULT_MIN_SOLIDITY = 0.55             # filters thin annulus/wall-ring artifacts
DEFAULT_MAX_ASPECT_RATIO = 12.0         # filters long thin noise (dimension lines)
DEFAULT_DUPLICATE_AREA_RATIO = 0.90     # child ~same area as parent => double wall


def _scaled_odd(value: float) -> int:
    """Round to nearest odd int >= 3 (required for adaptiveThreshold blockSize)."""
    v = int(round(value))
    if v < 3:
        v = 3
    if v % 2 == 0:
        v += 1
    return v


def _preprocess(image: np.ndarray, scale_factor: float) -> np.ndarray:
    """
    Build a clean binary wall mask, scaled for the image's resolution.

    scale_factor lets kernel/threshold sizes grow with resolution instead of
    being fixed constants — a fixed 5x5 kernel that's fine at 800px is far
    too small to bridge gaps at 4000px, and far too aggressive at 400px.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    blur_ksize = _scaled_odd(3 * scale_factor)
    blurred = cv2.GaussianBlur(gray, (blur_ksize, blur_ksize), 0)

    block_size = _scaled_odd(15 * scale_factor)
    threshold = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV,
        block_size, 2,
    )

    # Remove small noise (text glyphs, dimension tick marks, furniture
    # hatching) BEFORE closing gaps, via a small opening pass. Text strokes
    # are thin and get eaten by erosion; wall lines survive because they're
    # thicker and reinforced by the closing step that follows.
    open_ksize = max(2, int(round(2 * scale_factor)))
    open_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (open_ksize, open_ksize))
    opened = cv2.morphologyEx(threshold, cv2.MORPH_OPEN, open_kernel, iterations=1)

    # Bridge gaps in wall lines so room boundaries are fully enclosed.
    close_ksize = max(3, int(round(5 * scale_factor)))
    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (close_ksize, close_ksize))
    closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, close_kernel, iterations=2)

    return closed


def _solidity(contour) -> float:
    area = cv2.contourArea(contour)
    if area <= 0:
        return 0.0
    hull = cv2.convexHull(contour)
    hull_area = cv2.contourArea(hull)
    if hull_area <= 0:
        return 0.0
    return area / hull_area


def _aspect_ratio(contour) -> float:
    _, (w, h), _ = cv2.minAreaRect(contour)
    if min(w, h) <= 0:
        return float("inf")
    return max(w, h) / min(w, h)


def _adaptive_epsilon(perimeter: float, area: float) -> float:
    """
    Smaller rooms need a tighter epsilon or their corners get chewed away;
    larger rooms can tolerate the usual 2% of perimeter. Scale epsilon down
    for small areas instead of using one fixed coefficient for every room
    size.
    """
    if area < 2000:
        coeff = 0.008
    elif area < 10000:
        coeff = 0.013
    else:
        coeff = 0.02
    return max(1.5, coeff * perimeter)


def _collect_room_candidates(contours, hierarchy, floor_idx, min_area, max_area):
    """
    Walk the full hierarchy tree under the floor boundary (not just direct
    children), so nested rooms — e.g. a closet whose contour ends up as a
    child of its containing bedroom's contour — are still captured.

    Guards against the classic double-wall artifact: when walls are drawn
    with real thickness, cv2 can find both the room's inner boundary and an
    outer boundary that's nearly the same shape/area one level up. If a
    child's area is suspiciously close to its parent's, it's treated as the
    same physical room and only one is kept.
    """
    area_by_idx = {i: cv2.contourArea(c) for i, c in enumerate(contours)}
    candidates = []

    def children_of(idx):
        child = hierarchy[idx][2]
        out = []
        while child != -1:
            out.append(child)
            child = hierarchy[child][0]  # next sibling
        return out

    # BFS from the floor boundary, descending through all nesting levels.
    stack = children_of(floor_idx)
    visited = set()

    while stack:
        idx = stack.pop()
        if idx in visited:
            continue
        visited.add(idx)

        area = area_by_idx[idx]
        parent = hierarchy[idx][3]
        parent_area = area_by_idx.get(parent, 0)

        is_duplicate_of_parent = (
            parent_area > 0
            and parent != floor_idx
            and area / parent_area > DEFAULT_DUPLICATE_AREA_RATIO
        )

        if min_area <= area <= max_area and not is_duplicate_of_parent:
            candidates.append(idx)

        # Keep descending regardless, so a genuine small nested room behind
        # a duplicate/artifact contour still gets found.
        stack.extend(children_of(idx))

    return candidates


def process_floorplan(
    image_bytes: bytes,
    max_dim_for_processing: int = DEFAULT_MAX_DIM_FOR_PROCESSING,
    min_room_area_px: int = DEFAULT_MIN_ROOM_AREA_PX,
    min_room_area_frac: float = DEFAULT_MIN_ROOM_AREA_FRAC,
    max_room_area_frac: float = DEFAULT_MAX_ROOM_AREA_FRAC,
    min_solidity: float = DEFAULT_MIN_SOLIDITY,
    max_aspect_ratio: float = DEFAULT_MAX_ASPECT_RATIO,
) -> dict:
    """
    Process a floor plan image and extract room polygons.

    Pipeline:
        Image bytes -> (downscale if huge) -> Grayscale -> Blur
        -> Adaptive Threshold -> Denoise (open) -> Morphological Close
        -> Find Contours (RETR_TREE, full hierarchy walk)
        -> Filter by area / solidity / aspect ratio / duplicate-parent
        -> Adaptive polygon approximation -> rescale coords to original size

    Args:
        image_bytes: Raw image file bytes (PNG or JPG).
        max_dim_for_processing: Images larger than this (on the long side)
            are downscaled for contour detection, then coordinates are
            rescaled back up. Keeps large CAD-export floor plans fast
            without losing precision in the returned polygons.
        min_room_area_px: Absolute pixel-area floor for a room, protects
            genuinely tiny rooms (closets/bathrooms) in floor plans with
            many rooms, where a percentage-only cutoff would remove them.
        min_room_area_frac / max_room_area_frac: Area bounds as a fraction
            of total image area.
        min_solidity: Contours with area/convex-hull-area below this are
            treated as wall-ring or clutter artifacts and dropped.
        max_aspect_ratio: Contours thinner/longer than this (dimension
            lines, stray strokes) are dropped.

    Returns:
        dict with keys: image_width, image_height, rooms (list of dicts,
        each with id, name, polygon, area, centroid, bbox).
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Could not decode image. Ensure it is a valid PNG or JPG.")

    orig_height, orig_width = image.shape[:2]
    logger.info("Image loaded: %dx%d", orig_width, orig_height)

    # --- Downscale very large images for contour detection ---
    long_side = max(orig_width, orig_height)
    rescale = 1.0
    proc_image = image
    if long_side > max_dim_for_processing:
        rescale = max_dim_for_processing / long_side
        proc_image = cv2.resize(
            image, None, fx=rescale, fy=rescale, interpolation=cv2.INTER_AREA
        )
        logger.info("Downscaled to %dx%d for processing (factor %.3f)",
                     proc_image.shape[1], proc_image.shape[0], rescale)

    proc_height, proc_width = proc_image.shape[:2]
    total_area = proc_width * proc_height

    # scale_factor lets kernel sizes adapt to whatever resolution we ended
    # up processing at, using 1000px as the reference point.
    scale_factor = max(0.5, proc_width / 1000.0)

    closed = _preprocess(proc_image, scale_factor)

    contours, hierarchy = cv2.findContours(
        closed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )

    if hierarchy is None or len(contours) == 0:
        logger.warning("No contours found")
        return {"image_width": orig_width, "image_height": orig_height, "rooms": []}

    hierarchy = hierarchy[0]
    logger.info("Found %d raw contours", len(contours))

    top_level_indices = [i for i in range(len(contours)) if hierarchy[i][3] == -1]
    if not top_level_indices:
        logger.warning("No top-level contours found")
        return {"image_width": orig_width, "image_height": orig_height, "rooms": []}

    floor_idx = max(top_level_indices, key=lambda i: cv2.contourArea(contours[i]))

    min_area = max(
        min_room_area_px * (rescale ** 2),  # keep absolute floor in processing scale
        total_area * min_room_area_frac,
    )
    max_area = total_area * max_room_area_frac

    candidate_indices = _collect_room_candidates(
        contours, hierarchy, floor_idx, min_area, max_area
    )

    rooms = []
    room_id = 1
    inv_rescale = 1.0 / rescale

    for i in candidate_indices:
        contour = contours[i]

        if _solidity(contour) < min_solidity:
            continue
        if _aspect_ratio(contour) > max_aspect_ratio:
            continue

        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        epsilon = _adaptive_epsilon(perimeter, area)
        approx = cv2.approxPolyDP(contour, epsilon, True)

        if len(approx) < 3:
            continue

        pts = approx.reshape(-1, 2).astype(np.float64)
        pts *= inv_rescale  # back to original image coordinates
        polygon = [[int(round(x)), int(round(y))] for x, y in pts]

        x, y, w, h = cv2.boundingRect(contour)
        bbox = [
            int(round(x * inv_rescale)), int(round(y * inv_rescale)),
            int(round(w * inv_rescale)), int(round(h * inv_rescale)),
        ]
        moments = cv2.moments(contour)
        if moments["m00"] != 0:
            cx = moments["m10"] / moments["m00"] * inv_rescale
            cy = moments["m01"] / moments["m00"] * inv_rescale
        else:
            cx, cy = bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2

        rooms.append({
            "id": room_id,
            "name": f"Room {room_id}",
            "polygon": polygon,
            "area": round(area * (inv_rescale ** 2), 1),
            "centroid": [round(cx, 1), round(cy, 1)],
            "bbox": bbox,
        })
        room_id += 1

    logger.info("Extracted %d rooms", len(rooms))

    return {
        "image_width": orig_width,
        "image_height": orig_height,
        "rooms": rooms,
    }


def draw_rooms_on_image(image_bytes: bytes, rooms: list) -> bytes:
    """
    Draw room polygons onto the original image for debugging / preview.

    Args:
        image_bytes: Raw image file bytes.
        rooms: List of room dicts with 'polygon' key.

    Returns:
        JPEG image bytes with polygons drawn.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Could not decode image.")

    overlay = image.copy()
    rng = np.random.default_rng(42)  # stable colors across calls

    for room in rooms:
        pts = np.array(room["polygon"], dtype=np.int32)
        color = tuple(int(c) for c in rng.integers(80, 230, size=3))
        cv2.fillPoly(overlay, [pts], color)
        cv2.polylines(image, [pts], True, (0, 0, 0), 2)

        label = room.get("name", str(room.get("id", "")))
        cx, cy = room.get("centroid", [pts[:, 0].mean(), pts[:, 1].mean()])
        cv2.putText(
            image, label, (int(cx) - 20, int(cy)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA,
        )

    alpha = 0.35
    cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)

    _, buf = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return buf.tobytes()