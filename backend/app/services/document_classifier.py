"""
Document Type Classifier.

Given OCR blocks from ALL pages, scores keyword + pattern evidence for each
known document type and returns the best match with a rough confidence.

Pure keyword/pattern heuristic -- not a trained model. Deliberately
conservative: returns "unknown" rather than guessing when evidence is weak
or tied, since routing an image through the WRONG type's field-extraction
logic would produce confidently-wrong output, which is worse than admitting
"I don't know."
"""

import re
from typing import List, Literal, Tuple

from app.schemas import OCRBlock

DocumentType = Literal["driving_licence", "aadhaar_card", "unknown"]

AADHAAR_NUMBER_PATTERN = re.compile(r'\b([2-9]\d{3})\s?(\d{4})\s?(\d{4})\b')
DL_NUMBER_PATTERN = re.compile(r'\b[A-Z]{2}[0-9]{2}[0-9A-Z]{6,13}\b')

AADHAAR_KEYWORDS = [
    "aadhaar", "aadhar", "uidai", "unique identification authority",
    "government of india", "mera aadhaar meri pehchan"
]
DL_KEYWORDS = [
    "driving licence", "driving license", "union of india", "transport",
    "form 7", "mcwg", "lmv", "date of issue", "validity"
]


def classify_document(blocks: List[OCRBlock]) -> Tuple[DocumentType, float]:
    """
    Returns (document_type, confidence). Confidence is a rough
    evidence-strength ratio in [0, 1], NOT a calibrated probability --
    treat it as "how lopsided was the evidence", not "% chance correct".
    """
    if not blocks:
        return "unknown", 0.0

    full_text = " ".join(b.text.lower() for b in blocks)
    full_text_upper = full_text.upper()

    aadhaar_score = 0
    dl_score = 0

    for kw in AADHAAR_KEYWORDS:
        if kw in full_text:
            aadhaar_score += 2
    for kw in DL_KEYWORDS:
        if kw in full_text:
            dl_score += 2

    if AADHAAR_NUMBER_PATTERN.search(full_text):
        aadhaar_score += 3
    if DL_NUMBER_PATTERN.search(full_text_upper):
        dl_score += 2  # weaker alone -- this shape can coincidentally appear elsewhere

    total = aadhaar_score + dl_score
    if total == 0 or aadhaar_score == dl_score:
        return "unknown", 0.0 if total == 0 else 0.5

    if aadhaar_score > dl_score:
        return "aadhaar_card", round(aadhaar_score / total, 2)
    return "driving_licence", round(dl_score / total, 2)