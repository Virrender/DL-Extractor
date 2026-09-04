import cv2
import numpy as np


MIN_WIDTH = 300
MIN_HEIGHT = 200

MIN_BLUR_SCORE = 40.0

MIN_BRIGHTNESS = 40.0
MAX_BRIGHTNESS = 220.0


def calculate_blur_score(image):
    """
    Calculate image sharpness using the variance
    of the Laplacian.
    """

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

    return cv2.Laplacian(
        gray,
        cv2.CV_64F
    ).var()


def calculate_brightness(image):
    """
    Calculate the average brightness of the image.
    """

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

    return float(
        np.mean(gray)
    )


def check_image_quality(image):
    """
    Check whether an image is suitable for OCR.
    """

    height, width = image.shape[:2]

    if width < MIN_WIDTH or height < MIN_HEIGHT:
        return {
            "acceptable": False,
            "reason": "Image resolution is too low",
            "width": width,
            "height": height
        }

    blur_score = calculate_blur_score(image)

    if blur_score < MIN_BLUR_SCORE:
        return {
            "acceptable": False,
            "reason": "Image is too blurry",
            "width": width,
            "height": height,
            "blur_score": blur_score
        }

    brightness = calculate_brightness(image)

    if brightness < MIN_BRIGHTNESS:
        return {
            "acceptable": False,
            "reason": "Image is too dark",
            "width": width,
            "height": height,
            "blur_score": blur_score,
            "brightness": brightness
        }

    if brightness > MAX_BRIGHTNESS:
        return {
            "acceptable": False,
            "reason": "Image is too bright",
            "width": width,
            "height": height,
            "blur_score": blur_score,
            "brightness": brightness
        }

    return {
        "acceptable": True,
        "width": width,
        "height": height,
        "blur_score": blur_score,
        "brightness": brightness
    }