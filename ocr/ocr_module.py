"""
ocr/ocr_module.py
─────────────────
Extracts raw text from a prescription image using EasyOCR + OpenCV preprocessing.
Falls back to pytesseract if EasyOCR is unavailable.
"""

import os
import cv2
import numpy as np
from PIL import Image


# ── EasyOCR reader (lazy-loaded so the app starts faster) ──────────────────
_easyocr_reader = None

def _get_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            import easyocr
            _easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        except ImportError:
            _easyocr_reader = False          # mark as unavailable
    return _easyocr_reader


# ── Image pre-processing ───────────────────────────────────────────────────
def preprocess_image(image_path: str) -> np.ndarray:
    """
    Apply OpenCV preprocessing to improve OCR accuracy on prescription images.
    Steps: grayscale → denoise → adaptive threshold → deskew
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Cannot read image at {image_path}")

    # 1. Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. Upscale small images (better OCR on low-res scans)
    h, w = gray.shape
    if max(h, w) < 1000:
        scale = 1000 / max(h, w)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # 3. Denoise
    gray = cv2.fastNlMeansDenoising(gray, h=10)

    # 4. Adaptive thresholding (handles uneven lighting on paper)
    processed = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 21, 10
    )

    # 5. Deskew
    processed = _deskew(processed)

    return processed


def _deskew(image: np.ndarray) -> np.ndarray:
    """Correct slight rotations in scanned documents."""
    coords = np.column_stack(np.where(image > 0))
    if len(coords) == 0:
        return image
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.5:        # skip tiny corrections
        return image
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(image, M, (w, h),
                          flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)


# ── Main OCR function ──────────────────────────────────────────────────────
def extract_text(image_path: str) -> dict:
    """
    Extract text from a prescription image.

    Returns:
        {
            "text": str,           # full extracted text
            "engine": str,         # "easyocr" | "tesseract" | "error"
            "confidence": float,   # 0–1 average confidence (EasyOCR only)
            "error": str | None
        }
    """
    if not os.path.exists(image_path):
        return {"text": "", "engine": "error", "confidence": 0.0,
                "error": f"File not found: {image_path}"}

    try:
        processed = preprocess_image(image_path)
    except Exception as e:
        return {"text": "", "engine": "error", "confidence": 0.0, "error": str(e)}

    # ── Try EasyOCR first ──────────────────────────────────────────────────
    reader = _get_reader()
    if reader:
        try:
            results = reader.readtext(processed)
            lines = []
            confidences = []
            for (_bbox, text, conf) in results:
                text = text.strip()
                if text:
                    lines.append(text)
                    confidences.append(conf)
            full_text = "\n".join(lines)
            avg_conf = float(np.mean(confidences)) if confidences else 0.0
            return {
                "text": full_text,
                "engine": "easyocr",
                "confidence": round(avg_conf, 3),
                "error": None
            }
        except Exception as e:
            pass   # fall through to tesseract

    # ── Fallback: pytesseract ──────────────────────────────────────────────
    try:
        import pytesseract
        pil_img = Image.fromarray(processed)
        config = r'--oem 3 --psm 6'
        full_text = pytesseract.image_to_string(pil_img, config=config)
        return {
            "text": full_text.strip(),
            "engine": "tesseract",
            "confidence": 0.0,
            "error": None
        }
    except Exception as e:
        return {
            "text": "",
            "engine": "error",
            "confidence": 0.0,
            "error": f"Both OCR engines failed. Last error: {e}"
        }


# ── CLI test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "test.jpg"
    result = extract_text(path)
    print(f"Engine : {result['engine']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Text:\n{result['text']}")
