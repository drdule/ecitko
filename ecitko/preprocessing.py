from pathlib import Path

import cv2
from PIL import Image


def crop_red_marked_roi(bgr_image):
    hsv = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)

    lower1 = (0, 70, 50)
    upper1 = (10, 255, 255)
    lower2 = (170, 70, 50)
    upper2 = (180, 255, 255)

    mask1 = cv2.inRange(hsv, lower1, upper1)
    mask2 = cv2.inRange(hsv, lower2, upper2)
    mask = cv2.bitwise_or(mask1, mask2)

    height, width = mask.shape[:2]
    border = max(10, int(0.03 * min(height, width)))
    safe_mask = mask.copy()
    safe_mask[:border, :] = 0
    safe_mask[-border:, :] = 0
    safe_mask[:, :border] = 0
    safe_mask[:, -border:] = 0

    contours, _ = cv2.findContours(safe_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return bgr_image, False

    best = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(best)

    if (w * h) >= int(0.85 * width * height):
        return bgr_image, False

    pad = int(0.08 * max(w, h)) + 10
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(bgr_image.shape[1], x + w + pad)
    y1 = min(bgr_image.shape[0], y + h + pad)
    return bgr_image[y0:y1, x0:x1], True


def _crop_red_roi(bgr_image):
    roi, _ = crop_red_marked_roi(bgr_image)
    return roi


def load_base_image_for_ocr(image_path: str) -> Image.Image:
    path = Path(image_path)
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"Unable to load image: {image_path}")

    roi_bgr, marked = crop_red_marked_roi(bgr)

    if marked:
        # Heuristic: consumption register is typically in the lower part of the marked ROI.
        h, w = roi_bgr.shape[:2]
        if h >= 240 and w >= 360:
            y0 = int(h * 0.35)
            y1 = int(h * 0.98)
            x0 = int(w * 0.04)
            x1 = int(w * 0.96)
            roi_bgr = roi_bgr[y0:y1, x0:x1]

        hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, (0, 70, 50), (10, 255, 255))
        mask2 = cv2.inRange(hsv, (170, 70, 50), (180, 255, 255))
        red_mask = cv2.bitwise_or(mask1, mask2)
        red_mask = cv2.dilate(red_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        roi_bgr[red_mask > 0] = (255, 255, 255)
    rgb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def preprocess_for_ocr(image_path: str) -> Image.Image:
    path = Path(image_path)
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"Unable to load image: {image_path}")

    roi_bgr, marked = crop_red_marked_roi(bgr)

    if marked:
        # Same heuristic crop as in load_base_image_for_ocr
        h, w = roi_bgr.shape[:2]
        if h >= 240 and w >= 360:
            y0 = int(h * 0.35)
            y1 = int(h * 0.98)
            x0 = int(w * 0.04)
            x1 = int(w * 0.96)
            roi_bgr = roi_bgr[y0:y1, x0:x1]

        hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, (0, 70, 50), (10, 255, 255))
        mask2 = cv2.inRange(hsv, (170, 70, 50), (180, 255, 255))
        red_mask = cv2.bitwise_or(mask1, mask2)
        red_mask = cv2.dilate(red_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        roi_bgr[red_mask > 0] = (255, 255, 255)
    image = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)

    denoised = cv2.bilateralFilter(image, d=9, sigmaColor=75, sigmaSpace=75)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast = clahe.apply(denoised)
    thresholded = cv2.adaptiveThreshold(
        contrast,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        8,
    )

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned = cv2.morphologyEx(thresholded, cv2.MORPH_OPEN, kernel)
    return Image.fromarray(cleaned)