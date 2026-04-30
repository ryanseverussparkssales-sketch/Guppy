"""
Vision-Grounded Screen Parsing Layer

Upgrades PC control from raw coordinate clicks to grounded, vision-understood UI actions.
Pattern: capture → parse → decide → ground action → safety gate → execute → trace

OmniParser v2 ONNX integration with MiniCPM vision fallback.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

try:
    from PIL import Image
    _PIL_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # Pillow is optional for API importability.
    Image = None  # type: ignore[assignment]
    _PIL_IMPORT_ERROR = exc

logger = logging.getLogger(__name__)

# ── Types ──────────────────────────────────────────────────────────────────

@dataclass
class UIElement:
    """Detected UI element with spatial and semantic information"""
    label: str
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    element_type: str  # button, input, link, text, image, etc.
    confidence: float  # 0.0–1.0

    def to_dict(self) -> dict:
        return asdict(self)


# ── Screen Capture ─────────────────────────────────────────────────────────

def capture_screen() -> Optional[Image.Image]:
    """
    Capture current screen using pyautogui.

    Returns:
        PIL Image of current screen, or None if pyautogui unavailable
    """
    try:
        if Image is None:
            raise RuntimeError(f"Pillow unavailable: {_PIL_IMPORT_ERROR}")
        import pyautogui
        screenshot = pyautogui.screenshot()
        return screenshot
    except Exception as e:
        logger.error(f"Failed to capture screen: {e}")
        return None


# ── OmniParser Integration ─────────────────────────────────────────────────

def _get_omniparser_model_path() -> Optional[Path]:
    """
    Resolve OmniParser model path.

    Checks in order:
    1. GUPPY_OMNIPARSER_MODEL_PATH env var
    2. C:\\guppy-models\\omniparser\\
    3. Home/.guppy/models/omniparser/

    Returns Path if found, None otherwise.
    """
    # Env var override
    if env_path := os.getenv('GUPPY_OMNIPARSER_MODEL_PATH'):
        path = Path(env_path)
        if path.exists():
            return path
        logger.warning(f"GUPPY_OMNIPARSER_MODEL_PATH set but not found: {path}")

    # Standard location
    standard_path = Path("C:\\guppy-models\\omniparser")
    if standard_path.exists():
        return standard_path

    # Home fallback
    home_path = Path.home() / ".guppy" / "models" / "omniparser"
    if home_path.exists():
        return home_path

    logger.debug("OmniParser model not found; will fall back to MiniCPM vision")
    return None


def _parse_screen_with_omniparser(image: Image.Image) -> list[UIElement]:
    """
    Parse screenshot using OmniParser ONNX model.

    OmniParser v2 returns structured UI element detection with OCR integration.
    """
    try:
        model_path = _get_omniparser_model_path()
        if not model_path:
            logger.debug("OmniParser not available, skipping")
            return []

        # Placeholder: actual OmniParser integration would go here
        # For now, return empty list to trigger MiniCPM fallback
        logger.debug("OmniParser integration placeholder — fallback to MiniCPM")
        return []

    except Exception as e:
        logger.error(f"OmniParser parsing failed: {e}")
        return []


# ── MiniCPM Vision Fallback ────────────────────────────────────────────────

def _parse_screen_with_minicpm(image: Image.Image) -> list[UIElement]:
    """
    Parse screenshot using MiniCPM vision (llamacpp-minicpm on port 8084).

    Sends screenshot to model with instruction to describe all visible UI elements
    and their approximate locations, then parses JSON response into UIElement list.
    """
    try:
        import base64
        import io

        import requests

        # Encode image to base64
        buf = io.BytesIO()
        image.save(buf, format="JPEG")
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        # Query MiniCPM vision model
        url = "http://localhost:8084/v1/chat/completions"
        payload = {
            "model": "llamacpp-minicpm",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Analyze this screenshot and describe all visible UI elements.
For each element, provide:
1. Label (button text, field name, etc.)
2. Element type (button, input, link, text, image, icon, menu, etc.)
3. Approximate bounding box as [x1, y1, x2, y2] (normalized 0.0-1.0)
4. Confidence (0.0-1.0)

Return as JSON: {"elements": [{"label": "...", "type": "...", "bbox": [...], "confidence": 0.9}]}
Only include elements that are interactive or informative. Ignore backgrounds."""
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                        }
                    ]
                }
            ],
            "temperature": 0.2,
            "max_tokens": 2048,
        }

        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()

        result = response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "{}")

        # Parse JSON response
        try:
            # Try to extract JSON from response text
            if isinstance(content, str):
                # Look for JSON block
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    json_str = content[start:end]
                    parsed = json.loads(json_str)
                else:
                    parsed = json.loads(content)
            else:
                parsed = content

            # Convert to UIElement list, denormalize bboxes to pixel coords
            image_w, image_h = image.size
            elements = []
            for elem_dict in parsed.get("elements", []):
                bbox = elem_dict.get("bbox", [0, 0, 1, 1])
                # Denormalize: [0.0-1.0] → pixel coordinates
                x1, y1, x2, y2 = bbox
                x1_px = int(x1 * image_w)
                y1_px = int(y1 * image_h)
                x2_px = int(x2 * image_w)
                y2_px = int(y2 * image_h)

                elem = UIElement(
                    label=elem_dict.get("label", ""),
                    bbox=(x1_px, y1_px, x2_px, y2_px),
                    element_type=elem_dict.get("type", "unknown"),
                    confidence=float(elem_dict.get("confidence", 0.5))
                )
                if elem.label and elem.confidence > 0.3:
                    elements.append(elem)

            logger.info(f"Parsed {len(elements)} UI elements via MiniCPM")
            return elements

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse MiniCPM response as JSON: {e}")
            logger.debug(f"Response content: {content}")
            return []

    except Exception as e:
        logger.error(f"MiniCPM vision parsing failed: {e}")
        return []


# ── Public API ──────────────────────────────────────────────────────────────

def parse_screen(image: Image.Image) -> list[UIElement]:
    """
    Parse screenshot to extract UI elements.

    Tries OmniParser first (if model available), falls back to MiniCPM vision.

    Args:
        image: PIL Image of screenshot

    Returns:
        List of detected UI elements, empty list if parsing fails
    """
    if not image:
        return []
    if Image is None:
        logger.error("Cannot parse screen because Pillow is unavailable: %s", _PIL_IMPORT_ERROR)
        return []

    # Try OmniParser first
    elements = _parse_screen_with_omniparser(image)
    if elements:
        return elements

    # Fall back to MiniCPM vision
    elements = _parse_screen_with_minicpm(image)
    return elements


def find_element(elements: list[UIElement], description: str) -> Optional[UIElement]:
    """
    Find best-matching UI element by fuzzy text search.

    Args:
        elements: List of detected UI elements
        description: Natural language description (e.g., "Submit button")

    Returns:
        Best matching UIElement or None
    """
    if not elements or not description:
        return None

    description = description.lower()

    # Simple fuzzy match: score based on substring overlap + confidence
    best_match = None
    best_score = 0.0

    for elem in elements:
        label = (elem.label or "").lower()
        elem_type = (elem.element_type or "").lower()

        # Substring overlap score
        overlap_score = 0.0
        for word in description.split():
            if word in label or word in elem_type:
                overlap_score += 0.5

        # Combined score: overlap + confidence
        score = overlap_score * 0.7 + elem.confidence * 0.3

        if score > best_score:
            best_score = score
            best_match = elem

    if best_match and best_score >= 0.3:
        logger.debug(f"Matched '{description}' to '{best_match.label}' (score={best_score:.2f})")
        return best_match

    logger.warning(f"No suitable match found for '{description}'")
    return None


def ground_click(description: str, elements: Optional[list[UIElement]] = None) -> Optional[tuple[int, int]]:
    """
    Ground a click action to pixel coordinates.

    If elements not provided, captures screen and parses on the fly.

    Args:
        description: What to click (e.g., "OK button")
        elements: Pre-parsed UI elements (optional)

    Returns:
        Tuple (x, y) for click, or None if element not found
    """
    # Capture and parse if needed
    if not elements:
        image = capture_screen()
        if not image:
            logger.error("Could not capture screen for grounding")
            return None
        elements = parse_screen(image)

    # Find matching element
    elem = find_element(elements, description)
    if not elem:
        return None

    # Return center of bounding box
    x1, y1, x2, y2 = elem.bbox
    x = (x1 + x2) // 2
    y = (y1 + y2) // 2

    logger.info(f"Grounded '{description}' to ({x}, {y})")
    return (x, y)
