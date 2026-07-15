"""
OpenCV-based floor plan processing service.

Detects enclosed rooms by analyzing walls and contours in floor plan images.
Uses a classical computer vision pipeline — no AI/LLM APIs.
"""

import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)


def process_floorplan(image_bytes: bytes) -> dict:
    """
    Process a floor plan image and extract room polygons.

    Pipeline:
        Image bytes -> Grayscale -> Gaussian Blur -> Adaptive Threshold
        -> Morphological Close -> Find Contours (RETR_TREE with hierarchy)
        -> Filter by hierarchy depth -> Polygon Approximation
        -> Return polygon coordinates

    Uses RETR_TREE so that both the outer floor boundary and all internal
    room boundaries are captured. The hierarchy array tells us which
    contours are children (rooms) of the outer floor contour.

    Args:
        image_bytes: Raw image file bytes (PNG or JPG).

    Returns:
        dict with keys: image_width, image_height, rooms (list of dicts).
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Could not decode image. Ensure it is a valid PNG or JPG.")

    height, width = image.shape[:2]
    total_area = width * height
    logger.info("Image loaded: %dx%d", width, height)

    # --- Preprocessing ---
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Adaptive threshold converts the image to black-and-white.
    # Walls become white (255), room interiors become black (0).
    threshold = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
    )

    # Morphological close to bridge small gaps in walls so contours are
    # fully enclosed.  Without this, thin wall segments can leave gaps
    # that break a room into multiple fragmented contours.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(threshold, cv2.MORPH_CLOSE, kernel, iterations=2)

    # --- Contour detection with full hierarchy ---
    # RETR_TREE returns every contour plus a hierarchy array.
    # hierarchy[i] = [next, prev, first_child, parent]
    # A contour with parent == -1 is top-level (the outer floor boundary).
    # Direct children of that top-level contour are the rooms.
    contours, hierarchy = cv2.findContours(
        closed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
    )

    if hierarchy is None or len(contours) == 0:
        logger.warning("No contours found")
        return {"image_width": width, "image_height": height, "rooms": []}

    hierarchy = hierarchy[0]  # shape (N, 4) — flatten batch dim
    logger.info("Found %d raw contours", len(contours))

    # --- Find the outer floor boundary (top-level, largest area) ---
    top_level_indices = [
        i for i in range(len(contours)) if hierarchy[i][3] == -1
    ]

    if not top_level_indices:
        logger.warning("No top-level contours found")
        return {"image_width": width, "image_height": height, "rooms": []}

    # Pick the largest top-level contour as the floor boundary
    floor_idx = max(top_level_indices, key=lambda i: cv2.contourArea(contours[i]))

    # --- Collect rooms: direct children of the floor boundary ---
    min_area = total_area * 0.001  # rooms can be small
    max_area = total_area * 0.85   # nothing except the floor itself

    rooms = []
    room_id = 1

    for i in range(len(contours)):
        # Only accept contours whose parent is the floor boundary (depth 1)
        if hierarchy[i][3] != floor_idx:
            continue

        area = cv2.contourArea(contours[i])

        if area < min_area or area > max_area:
            continue

        # Approximate the contour to a polygon with fewer vertices
        perimeter = cv2.arcLength(contours[i], True)
        epsilon = 0.02 * perimeter
        approx = cv2.approxPolyDP(contours[i], epsilon, True)

        if len(approx) < 3:
            continue

        polygon = approx.reshape(-1, 2).tolist()
        polygon = [[int(pt[0]), int(pt[1])] for pt in polygon]

        rooms.append({
            "id": room_id,
            "name": f"Room {room_id}",
            "polygon": polygon,
        })
        room_id += 1

    logger.info("Extracted %d rooms", len(rooms))

    return {
        "image_width": width,
        "image_height": height,
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

    for room in rooms:
        pts = np.array(room["polygon"], dtype=np.int32)
        cv2.fillPoly(overlay, [pts], (255, 180, 0))
        cv2.polylines(image, [pts], True, (0, 0, 0), 2)

    alpha = 0.3
    cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)

    _, buf = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return buf.tobytes()
