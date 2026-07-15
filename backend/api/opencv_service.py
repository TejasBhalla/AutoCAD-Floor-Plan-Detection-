"""
Industrial Floor Plan Parser

Designed for complex OT/Industrial floor plans.

Pipeline

Image
    ↓
Preprocessing
    ↓
Wall Extraction
    ↓
Gap Closing
    ↓
Connected Components
    ↓
Room Extraction
    ↓
Polygon Generation
"""

from __future__ import annotations

import cv2
import numpy as np
import logging
from dataclasses import dataclass
from typing import List, Tuple

logger = logging.getLogger(__name__)


# -------------------------------------------------------
# Configuration
# -------------------------------------------------------

@dataclass
class ParserConfig:

    max_processing_size: int = 2200

    adaptive_block_size: int = 25

    adaptive_c: int = 5

    gaussian_kernel: int = 5

    wall_kernel: int = 7

    bridge_iterations: int = 3

    min_component_area: int = 120

    min_room_area: int = 800

    max_room_area_ratio: float = 0.90

    polygon_epsilon: float = 0.015

    remove_text: bool = True

    debug: bool = False


DEFAULT_CONFIG = ParserConfig()


# -------------------------------------------------------
# Utilities
# -------------------------------------------------------

def resize_for_processing(image, max_size):

    h, w = image.shape[:2]

    longest = max(h, w)

    if longest <= max_size:
        return image, 1.0

    scale = max_size / longest

    resized = cv2.resize(
        image,
        None,
        fx=scale,
        fy=scale,
        interpolation=cv2.INTER_AREA,
    )

    return resized, scale


def odd(value):

    value = int(value)

    if value % 2 == 0:
        value += 1

    return max(value, 3)


# -------------------------------------------------------
# Load image
# -------------------------------------------------------

def load_image(image_bytes):

    data = np.frombuffer(image_bytes, np.uint8)

    image = cv2.imdecode(data, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Unable to decode image.")

    return image


# -------------------------------------------------------
# Preprocessing
# -------------------------------------------------------

def preprocess(image, config=DEFAULT_CONFIG):

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    blur = cv2.GaussianBlur(
        gray,
        (odd(config.gaussian_kernel), odd(config.gaussian_kernel)),
        0,
    )

    binary = cv2.adaptiveThreshold(
        blur,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        odd(config.adaptive_block_size),
        config.adaptive_c,
    )

    return binary


# -------------------------------------------------------
# Remove tiny symbols
# -------------------------------------------------------

def remove_small_components(binary, config=DEFAULT_CONFIG):

    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary)

    clean = np.zeros_like(binary)

    for i in range(1, count):

        area = stats[i, cv2.CC_STAT_AREA]

        if area >= config.min_component_area:
            clean[labels == i] = 255

    return clean


# -------------------------------------------------------
# Extract horizontal / vertical walls
# -------------------------------------------------------

def extract_walls(binary):

    horizontal_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (45, 1),
    )

    vertical_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (1, 45),
    )

    horizontal = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        horizontal_kernel,
    )

    vertical = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        vertical_kernel,
    )

    walls = cv2.bitwise_or(horizontal, vertical)

    return walls


# -------------------------------------------------------
# Bridge wall gaps
# -------------------------------------------------------

def bridge_wall_gaps(walls, config=DEFAULT_CONFIG):

    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (config.wall_kernel, config.wall_kernel),
    )

    closed = cv2.morphologyEx(
        walls,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=config.bridge_iterations,
    )

    return closed


# -------------------------------------------------------
# Debug helper
# -------------------------------------------------------

def show(title, image, config=DEFAULT_CONFIG):

    if not config.debug:
        return

    cv2.imshow(title, image)
    cv2.waitKey(0)

# -------------------------------------------------------
# Fill wall thickness
# -------------------------------------------------------

def thicken_walls(walls):

    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (3, 3)
    )

    walls = cv2.dilate(
        walls,
        kernel,
        iterations=2
    )

    return walls


# -------------------------------------------------------
# Free Space Detection
# -------------------------------------------------------

def compute_free_space(walls):

    """
    Invert wall image.

    White = walkable/room space
    Black = walls
    """

    return cv2.bitwise_not(walls)


# -------------------------------------------------------
# Remove outside region
# -------------------------------------------------------

def remove_outside_region(free_space):

    """
    Flood fill only once from (0,0).

    This removes the outside of the building while
    preserving enclosed rooms.
    """

    h, w = free_space.shape

    flood = free_space.copy()

    mask = np.zeros((h + 2, w + 2), np.uint8)

    cv2.floodFill(
        flood,
        mask,
        (0, 0),
        0
    )

    return flood


# -------------------------------------------------------
# Connected Components
# -------------------------------------------------------

def detect_room_components(
    free_space,
    config=DEFAULT_CONFIG
):

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        free_space,
        connectivity=8
    )

    rooms = []

    total_area = free_space.shape[0] * free_space.shape[1]

    max_room_area = total_area * config.max_room_area_ratio

    room_id = 1

    for label in range(1, num_labels):

        area = stats[label, cv2.CC_STAT_AREA]

        if area < config.min_room_area:
            continue

        if area > max_room_area:
            continue

        x = stats[label, cv2.CC_STAT_LEFT]
        y = stats[label, cv2.CC_STAT_TOP]
        w = stats[label, cv2.CC_STAT_WIDTH]
        h = stats[label, cv2.CC_STAT_HEIGHT]

        component = np.zeros_like(free_space)

        component[labels == label] = 255

        rooms.append({

            "id": room_id,

            "bbox": (x, y, w, h),

            "area": int(area),

            "mask": component

        })

        room_id += 1

    logger.info(
        "Detected %d room candidates",
        len(rooms)
    )

    return rooms

# -------------------------------------------------------
# Remove thin structures
# -------------------------------------------------------

def remove_thin_structures(binary):

    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (2,2)
    )

    opened = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        kernel,
        iterations=1
    )

    return opened

# -------------------------------------------------------
# Reject unlikely rooms
# -------------------------------------------------------

def filter_rooms(
    rooms,
    config=DEFAULT_CONFIG
):

    filtered = []

    for room in rooms:

        x,y,w,h = room["bbox"]

        area = room["area"]

        aspect = w / float(h)

        fill_ratio = area / float(w*h)

        if aspect > 8:
            continue

        if aspect < 0.12:
            continue

        if fill_ratio < 0.25:
            continue

        filtered.append(room)

    logger.info(
        "%d rooms remaining",
        len(filtered)
    )

    return filtered

# -------------------------------------------------------
# Segment Rooms
# -------------------------------------------------------

def segment_rooms(
    binary,
    config=DEFAULT_CONFIG
):

    clean = remove_small_components(
        binary,
        config
    )

    walls = extract_walls(clean)

    walls = bridge_wall_gaps(
        walls,
        config
    )

    walls = thicken_walls(
        walls
    )

    free_space = compute_free_space(
        walls
    )

    free_space = remove_outside_region(
        free_space
    )

    free_space = remove_thin_structures(
        free_space
    )

    rooms = detect_room_components(
        free_space,
        config
    )

    rooms = filter_rooms(
        rooms,
        config
    )

    return rooms

# -------------------------------------------------------
# Largest contour from a room mask
# -------------------------------------------------------

def largest_contour(mask):

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_NONE
    )

    if not contours:
        return None

    return max(
        contours,
        key=cv2.contourArea
    )

# -------------------------------------------------------
# Simplify contour
# -------------------------------------------------------

def contour_to_polygon(
    contour,
    config=DEFAULT_CONFIG
):

    perimeter = cv2.arcLength(
        contour,
        True
    )

    epsilon = config.polygon_epsilon * perimeter

    approx = cv2.approxPolyDP(
        contour,
        epsilon,
        True
    )

    polygon = []

    for p in approx:

        x, y = p[0]

        polygon.append([
            int(x),
            int(y)
        ])

    return polygon

# -------------------------------------------------------
# Polygon centroid
# -------------------------------------------------------

def contour_centroid(contour):

    m = cv2.moments(contour)

    if m["m00"] == 0:

        x, y, w, h = cv2.boundingRect(contour)

        return (
            x + w // 2,
            y + h // 2
        )

    return (
        int(m["m10"] / m["m00"]),
        int(m["m01"] / m["m00"])
    )

# -------------------------------------------------------
# Bounding box
# -------------------------------------------------------

def contour_bbox(contour):

    x, y, w, h = cv2.boundingRect(contour)

    return (
        int(x),
        int(y),
        int(w),
        int(h)
    )

# -------------------------------------------------------
# Polygon area
# -------------------------------------------------------

def polygon_area(contour):

    return float(
        cv2.contourArea(contour)
    )

# -------------------------------------------------------
# Remove duplicate vertices
# -------------------------------------------------------

def clean_polygon(points):

    cleaned = []

    prev = None

    for p in points:

        if prev != p:

            cleaned.append(p)

        prev = p

    if len(cleaned) > 2:

        if cleaned[0] == cleaned[-1]:

            cleaned.pop()

    return cleaned

# -------------------------------------------------------
# Scale polygon
# -------------------------------------------------------

def scale_polygon(
    polygon,
    scale
):

    if scale == 1.0:

        return polygon

    scaled = []

    inv = 1.0 / scale

    for x, y in polygon:

        scaled.append([
            int(x * inv),
            int(y * inv)
        ])

    return scaled

# -------------------------------------------------------
# Convert masks to polygons
# -------------------------------------------------------

def extract_room_polygons(
    rooms,
    scale=1.0,
    config=DEFAULT_CONFIG
):

    output = []

    for room in rooms:

        contour = largest_contour(
            room["mask"]
        )

        if contour is None:
            continue

        polygon = contour_to_polygon(
            contour,
            config
        )

        polygon = clean_polygon(
            polygon
        )

        if len(polygon) < 3:
            continue

        polygon = scale_polygon(
            polygon,
            scale
        )

        cx, cy = contour_centroid(
            contour
        )

        if scale != 1:

            cx = int(cx / scale)
            cy = int(cy / scale)

        x, y, w, h = contour_bbox(
            contour
        )

        if scale != 1:

            inv = 1 / scale

            x = int(x * inv)
            y = int(y * inv)
            w = int(w * inv)
            h = int(h * inv)

        output.append({

            "id": room["id"],

            "name": f"Room {room['id']}",

            "polygon": polygon,

            "centroid": [cx, cy],

            "bbox": [x, y, w, h],

            "area": room["area"]

        })

    logger.info(
        "Generated %d polygons",
        len(output)
    )

    return output

# -------------------------------------------------------
# Merge adjacent rooms
# -------------------------------------------------------

def merge_small_rooms(
    rooms,
    distance_threshold=15
):

    merged = []

    used = set()

    for i, room in enumerate(rooms):

        if i in used:
            continue

        x1, y1 = room["centroid"]

        current = room

        for j, other in enumerate(rooms):

            if j <= i or j in used:
                continue

            x2, y2 = other["centroid"]

            d = np.sqrt(
                (x1-x2)**2 +
                (y1-y2)**2
            )

            if d < distance_threshold:

                used.add(j)

        merged.append(current)

    return merged

# -------------------------------------------------------
# Main Pipeline
# -------------------------------------------------------

def process_floorplan(
    image_bytes,
    config=DEFAULT_CONFIG
):
    """
    Returns

    {
        image_width,
        image_height,
        rooms
    }
    """

    image = load_image(image_bytes)

    original_h, original_w = image.shape[:2]

    image, scale = resize_for_processing(
        image,
        config.max_processing_size
    )

    logger.info(
        "Processing image %dx%d scale %.2f",
        original_w,
        original_h,
        scale
    )

    binary = preprocess(
        image,
        config
    )

    rooms = segment_rooms(
        binary,
        config
    )

    polygons = extract_room_polygons(
        rooms,
        scale,
        config
    )

    logger.info(
        "Detected %d rooms",
        len(polygons)
    )

    return {

        "image_width": original_w,

        "image_height": original_h,

        "room_count": len(polygons),

        "rooms": polygons

    }

def draw_rooms_on_image(
    image_bytes,
    rooms
):

    image = load_image(image_bytes)

    overlay = image.copy()

    colors = [

        (255,120,0),

        (0,180,255),

        (0,220,120),

        (255,80,180),

        (180,255,50),

    ]

    for room in rooms:

        color = colors[
            room["id"] % len(colors)
        ]

        pts = np.array(
            room["polygon"],
            np.int32
        )

        cv2.fillPoly(
            overlay,
            [pts],
            color
        )

        cv2.polylines(
            image,
            [pts],
            True,
            (0,0,0),
            2
        )

        x,y = room["centroid"]

        cv2.circle(
            image,
            (x,y),
            4,
            (0,0,255),
            -1
        )

        cv2.putText(

            image,

            room["name"],

            (x+6,y),

            cv2.FONT_HERSHEY_SIMPLEX,

            0.45,

            (0,0,0),

            1,

            cv2.LINE_AA

        )

    alpha = 0.35

    image = cv2.addWeighted(
        overlay,
        alpha,
        image,
        1-alpha,
        0
    )

    success, buffer = cv2.imencode(
        ".jpg",
        image
    )

    if not success:

        raise RuntimeError(
            "JPEG encoding failed"
        )

    return buffer.tobytes()

def room_statistics(
    rooms
):

    if not rooms:

        return {

            "count":0,

            "average_area":0,

            "largest_area":0

        }

    areas = [

        room["area"]

        for room in rooms

    ]

    return {

        "count":len(rooms),

        "average_area":float(

            np.mean(areas)

        ),

        "largest_area":float(

            np.max(areas)

        )

    }