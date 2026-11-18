"""Image processing utility functions.

Provides helpers for grayscale conversion, region cropping, non-maximum
suppression, debug overlays, timestamped screenshot saving, and pixel-level
image comparison.
"""
from __future__ import annotations

import datetime
from pathlib import Path

import cv2
import numpy as np


def to_grayscale(img: np.ndarray) -> np.ndarray:
    """Convert a BGR image to single-channel grayscale.

    Args:
        img: A 3-channel BGR image (H×W×3).

    Returns:
        A single-channel grayscale image (H×W).

    Raises:
        ValueError: If *img* does not have exactly 3 channels.
    """
    if img.ndim != 3 or img.shape[2] != 3:
        raise ValueError(
            f"Expected a 3-channel BGR image, got shape {img.shape}"
        )
    result: np.ndarray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return result


def crop_region(
    img: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
) -> np.ndarray:
    """Crop a rectangular region from *img* with bounds checking.

    Coordinates are clamped to the image dimensions so out-of-bounds
    values never cause an error.

    Args:
        img: Source image (any number of channels).
        x: Left column of the crop rectangle.
        y: Top row of the crop rectangle.
        w: Width of the crop rectangle.
        h: Height of the crop rectangle.

    Returns:
        The cropped sub-image.

    Raises:
        ValueError: If the clamped region has zero area.
    """
    img_h: int = img.shape[0]
    img_w: int = img.shape[1]

    x1: int = max(0, x)
    y1: int = max(0, y)
    x2: int = min(img_w, x + w)
    y2: int = min(img_h, y + h)

    if x2 <= x1 or y2 <= y1:
        raise ValueError(
            f"Crop region ({x}, {y}, {w}, {h}) results in zero area "
            f"for image of size ({img_w}, {img_h})"
        )

    cropped: np.ndarray = img[y1:y2, x1:x2].copy()
    return cropped


def non_max_suppression(
    boxes: np.ndarray,
    scores: np.ndarray,
    overlap_thresh: float = 0.3,
) -> list[int]:
    """Apply greedy non-maximum suppression to a set of bounding boxes.

    Boxes with high overlap relative to a higher-scoring box are discarded.

    Args:
        boxes: An ``(N, 4)`` array of bounding boxes in
               ``(x1, y1, x2, y2)`` format.
        scores: A 1-D array of confidence scores with length *N*.
        overlap_thresh: IoU threshold above which a box is suppressed.

    Returns:
        A list of integer indices into *boxes* that were kept.
    """
    if boxes.size == 0:
        return []

    # Work with floats for division.
    boxes_f: np.ndarray = boxes.astype(np.float64)

    x1: np.ndarray = boxes_f[:, 0]
    y1: np.ndarray = boxes_f[:, 1]
    x2: np.ndarray = boxes_f[:, 2]
    y2: np.ndarray = boxes_f[:, 3]

    areas: np.ndarray = (x2 - x1 + 1) * (y2 - y1 + 1)
    order: np.ndarray = scores.argsort()  # ascending

    keep: list[int] = []

    while order.size > 0:
        # Pick the box with the highest score (last in ascending order).
        i: int = int(order[-1])
        keep.append(i)

        # Compute IoU of the picked box with the rest.
        xx1: np.ndarray = np.maximum(x1[i], x1[order[:-1]])
        yy1: np.ndarray = np.maximum(y1[i], y1[order[:-1]])
        xx2: np.ndarray = np.minimum(x2[i], x2[order[:-1]])
        yy2: np.ndarray = np.minimum(y2[i], y2[order[:-1]])

        inter_w: np.ndarray = np.maximum(0.0, xx2 - xx1 + 1)
        inter_h: np.ndarray = np.maximum(0.0, yy2 - yy1 + 1)
        intersection: np.ndarray = inter_w * inter_h

        iou: np.ndarray = intersection / (
            areas[i] + areas[order[:-1]] - intersection
        )

        # Keep only boxes whose IoU is below the threshold.
        remaining: np.ndarray = np.where(iou <= overlap_thresh)[0]
        order = order[remaining]

    return keep


def draw_matches(
    img: np.ndarray,
    matches: list[tuple[int, int, int, int]],
    color: tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2,
) -> np.ndarray:
    """Draw rectangles on *img* for each match region (debug overlay).

    Args:
        img: Source image (modified in-place on a copy).
        matches: A list of ``(x, y, w, h)`` tuples.
        color: BGR color for the rectangles.
        thickness: Line thickness in pixels.

    Returns:
        A copy of *img* with rectangles drawn.
    """
    canvas: np.ndarray = img.copy()
    for x, y, w, h in matches:
        top_left: tuple[int, int] = (x, y)
        bottom_right: tuple[int, int] = (x + w, y + h)
        cv2.rectangle(canvas, top_left, bottom_right, color, thickness)
    return canvas


def save_debug_screenshot(
    img: np.ndarray,
    name: str,
    output_dir: Path | str = Path("debug"),
) -> Path:
    """Save *img* with a timestamp prefix for debugging.

    The output directory is created automatically if it does not exist.

    Args:
        img: The image to save.
        name: A descriptive base name (without extension).
        output_dir: Target directory for saved screenshots.

    Returns:
        The :class:`~pathlib.Path` to the written file.
    """
    out: Path = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    timestamp: str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename: str = f"{timestamp}_{name}.png"
    filepath: Path = out / filename

    cv2.imwrite(str(filepath), img)
    return filepath


def images_differ(
    img1: np.ndarray,
    img2: np.ndarray,
    threshold: float = 0.05,
) -> bool:
    """Determine whether two images differ beyond a given threshold.

    The comparison is based on the mean absolute pixel difference normalised
    to the ``[0, 1]`` range.

    Args:
        img1: First image.
        img2: Second image.  Must have the same shape as *img1*.
        threshold: Fractional threshold (0–1).  The images are considered
                   different if ``mean_abs_diff > threshold * 255``.

    Returns:
        ``True`` if the images differ by more than *threshold*.

    Raises:
        ValueError: If *img1* and *img2* have different shapes.
    """
    if img1.shape != img2.shape:
        raise ValueError(
            f"Image shapes do not match: {img1.shape} vs {img2.shape}"
        )

    diff: np.ndarray = cv2.absdiff(img1, img2)
    mean_diff: float = float(np.mean(diff))
    return mean_diff > threshold * 255
