"""
Shared extraction primitives reused across document types (Driving Licence,
Aadhaar Card, and any future ID document).
"""

import re
import datetime
from dataclasses import dataclass
from typing import List, Optional, Tuple, Literal

from app.schemas import OCRBlock, ExtractedField
from app.services.spatial_utils import (
    find_blocks_to_right, find_blocks_below, sort_blocks_in_reading_order
)


def compute_composite_score(ocr_conf: float, anchor_matched: bool, format_valid: bool) -> float:
    """Uncalibrated prototype evidence score — a discrete tier-based rank, not a probability."""
    if anchor_matched and format_valid:
        tier_base = 0.90
    elif format_valid and not anchor_matched:
        tier_base = 0.75
    elif anchor_matched and not format_valid:
        tier_base = 0.50
    else:
        tier_base = 0.30
    return round(min(1.0, max(0.0, tier_base + (ocr_conf * 0.10))), 2)


def is_label_boundary(text: str) -> bool:
    """
    Strict label matching to prevent false boundaries (e.g., 'name' in a sentence).
    Returns True if the block is definitively a field label, stop-word, or boilerplate.
    """
    clean = re.sub(r'[^a-z0-9]', '', text.lower())
    exact_labels = {
        "dob", "dateofbirth", "yearofbirth", "yob", "name", "holdername", "pin", "pincode",
        "address", "add", "bloodgroup", "bg", "signature", "sign",
        "signatureofholder", "signatureofissuingauthority", "authsignatory",
        "issuingauthority", "signatureofauthority", "issuedate", "expirydate",
        "dateofissue", "validtill", "validity", "holder", "holders",
        "dlno", "dlnumber", "licenceno", "licenseno", "drivinglicenceno",
        "aadhaarno", "aadharno", "uidaino", "vid", "gender", "sex",
        "father", "fathername", "husband", "husbandname", "mother", "mothername",
        "help", "helpdesk", "uidai", "1947"
    }
    if clean in exact_labels:
        return True

    # Stopwords/Footers in UIDAI and DL cards
    t_lower = text.lower()
    if any(k in t_lower for k in [
        "help@uidai", "www.uidai", "uidai.gov.in", "1947", "mera aadhaar", "meri pehchan"
    ]):
        return True

    # Any 12-digit Aadhaar number line is a boundary
    if re.search(r'\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b', text):
        return True

    tokens = set(re.findall(r'\b[a-z]+\b', text.lower()))
    if tokens.intersection({"signature", "signatory", "father", "husband", "mother", "holder"}):
        return True

    return False


def parse_calendar_date(text: str) -> Tuple[bool, Optional[str]]:
    """
    Validates and normalizes a date strictly using the calendar.
    Tolerates whitespace around separators (e.g. "01 / 01 / 1990"), which
    real-world OCR output on ID cards frequently produces.
    """
    match = re.search(r'\b(\d{1,2})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{4})\b', text)
    if not match:
        return False, None
    d, m, y = match.groups()
    try:
        dt = datetime.date(int(y), int(m), int(d))
        return True, dt.strftime("%Y-%m-%d")
    except ValueError:
        return False, None


def parse_year_only(text: str) -> Tuple[bool, Optional[str]]:
    """
    Fallback for documents that only print a birth YEAR (e.g. some older
    Aadhaar cards say "Year of Birth: 1990" with no full date). Returns an
    approximated YYYY-01-01 value — callers should only use this under an
    explicit "year of birth"/"yob" anchor to avoid matching unrelated
    4-digit numbers elsewhere on the card.
    """
    match = re.search(r'\b(19[0-9]{2}|20[0-9]{2})\b', text)
    if not match:
        return False, None
    year = int(match.group(1))
    if 1900 <= year <= datetime.date.today().year:
        return True, f"{year}-01-01"
    return False, None


def is_valid_name_part(text: str) -> bool:
    """Conservative check to reject obvious non-name text and multilingual OCR hallucinations."""
    # 1. Reject boundary labels
    if is_label_boundary(text):
        return False
        
    # 2. Reject Dates, PINs, Blood Groups, and DL structures
    if re.search(r'\b\d{1,2}[-/.]\s*\d{1,2}\s*[-/.]\d{4}\b', text):
        return False
    if re.search(r'\b\d{6}\b', text):
        return False
    if re.search(r'\b(A|B|AB|[O0])[\s]*[\(\[]?(\+|\-|pos|neg|positive|negative)', text, re.IGNORECASE):
        return False
        
    clean = re.sub(r'[^A-Z0-9]', '', text.upper())
    if re.match(r'^[ABO0][+-]$', clean):
        return False
    if re.match(r'^[A-Z]{2}[0-9A-Z]{4,15}$', clean) and any(c.isdigit() for c in clean):
        return False

    # 3. Reject non-Latin scripts (if OCR outputs actual Hindi/Tamil/Punjabi unicode)
    if any(ord(c) > 127 and c.isalpha() for c in text):
        return False

    # --- MULTILINGUAL HALLUCINATION & BOILERPLATE GUARDRAILS ---
    
    # 4. Reject boilerplate acronyms and common header keywords
    t_clean = re.sub(r'[^a-z0-9]', '', text.lower())
    if t_clean in {
        "hoh", "headofhousehold", "tehe", "union", "india", "government", "govt",
        "state", "licence", "license", "card", "authority", "uidai", "male", "female",
        "meraaadhaar", "meripehchan", "father", "husband", "mother", "signature", "holder"
    }:
        return False

    # 5. Reject single short tokens (<= 3 chars) which are often hallucinated icons or fragments
    words = text.strip().split()
    if len(words) == 1 and len(words[0]) <= 3:
        return False

    # 6. Reject typical OCR garbage symbols often hallucinated over foreign scripts
    if re.search(r'[\\;:!@#$%\^&*|]', text):
        return False
        
    # 7. Require at least 2 letters
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 2:
        return False
        
    # 8. Reject STRICTLY lowercase words.
    # Hallucinations of regional scripts by English OCR are almost always lowercase (e.g. "irar", "yja").
    # Real Aadhaar English names are Title Case or ALL CAPS.
    if all(c.islower() for c in letters):
        return False
        
    # 9. Length guardrail
    if len(text) > 50:
        return False
        
    return True

@dataclass
class FieldCandidate:
    raw_text: str
    normalized_value: str
    source_blocks: List[OCRBlock]
    anchor_relation: Literal["inline", "right", "below", "fallback"]
    distance_to_anchor: float
    ocr_confidence: float
    format_valid: bool

    def sort_key(self):
        # 'below' is ranked equally to 'right' so column layouts pick the date below the header
        # rather than jumping across columns. Proximity (-distance_to_anchor) breaks the tie.
        relation_score = {"inline": 3, "right": 2, "below": 2, "fallback": 0}[self.anchor_relation]
        return (1 if self.format_valid else 0, relation_score, -self.distance_to_anchor, self.ocr_confidence)


MIN_ACCEPTABLE_SCORE = 0.55


def gate_by_confidence(
    field: Optional[ExtractedField],
    min_score: float = MIN_ACCEPTABLE_SCORE
) -> Tuple[Optional[ExtractedField], Optional[str]]:
    """Rejects a field if its composite_score falls below the acceptance threshold."""
    if field is None:
        return None, None
    if field.composite_score < min_score:
        return None, f"Rejected low-confidence field (score={field.composite_score}, value='{field.value}')"
    return field, None


def extract_address(blocks: List[OCRBlock], source_page: Literal["front", "back"] = "back") -> Optional[ExtractedField]:
    """
    Generic address extraction: finds an 'address' anchor, then reads blocks
    below/right of it in reading order until a genuine label boundary or PIN code is reached.
    """
    if not blocks:
        return None
    anchors = ["address", "add:", "add :"]

    anchor_block = None
    for block in blocks:
        if any(a in block.text.lower() for a in anchors):
            anchor_block = block
            break

    if not anchor_block:
        return None

    # Guard against multi-column bleed (e.g. Punjabi address on left, English address on right)
    col_min_x = anchor_block.rect[0] - 40.0
    column_blocks = [b for b in blocks if b.rect[2] >= col_min_x]

    belows = find_blocks_below(anchor_block, column_blocks, require_horizontal_overlap=True, overlap_tolerance=120.0)
    rights = find_blocks_to_right(anchor_block, column_blocks)

    target_blocks = list({b.text: b for b in (belows + rights)}.values())
    sorted_blocks = sort_blocks_in_reading_order(target_blocks)

    address_texts = []
    final_blocks = []
    for b in sorted_blocks:
        if b is anchor_block:
            continue
            
        # Reject blocks that start far to the left of the column
        if b.rect[0] < col_min_x:
            continue

        # Stop at field label, footer, or helpline
        if is_label_boundary(b.text):
            break

        # Reject non-Latin characters (OCR hallucinations on regional scripts)
        if any(ord(c) > 127 for c in b.text):
            continue

        has_pin = bool(re.search(r'\b[1-9][0-9]{5}\b', b.text))

        clean_text = b.text.strip(" :,")
        # Strip PIN code from address text (it is extracted into its own field)
        clean_text = re.sub(r'\b[1-9][0-9]{5}\b', '', clean_text).strip(" :,")

        if clean_text:
            address_texts.append(clean_text)
            final_blocks.append(b)

        # On Indian documents, the PIN code is printed on the very last line of the address.
        # Any text below the PIN code is footer/signature boilerplate.
        if has_pin:
            break

    if not address_texts:
        return None

    bx = (min(b.rect[0] for b in final_blocks), min(b.rect[1] for b in final_blocks),
          max(b.rect[2] for b in final_blocks), max(b.rect[3] for b in final_blocks))

    conf = sum(b.ocr_confidence for b in final_blocks) / len(final_blocks)

    return ExtractedField(
        value=", ".join(address_texts),
        ocr_confidence=conf,
        anchor_matched=True,
        format_valid=True,
        composite_score=compute_composite_score(conf, True, True),
        raw_text=" ".join(b.text for b in final_blocks),
        bounding_box=bx,
        source_page=source_page
    )


def extract_pin_code(
    blocks: List[OCRBlock],
    address_field: Optional[ExtractedField],
    source_page: Literal["front", "back"] = "back"
) -> Optional[ExtractedField]:
    """Generic 6-digit Indian PIN code extraction, biased toward proximity to the address block."""
    candidates: List[FieldCandidate] = []

    addr_center_y = None
    addr_center_x = None
    if address_field and address_field.bounding_box:
        ax1, ay1, ax2, ay2 = address_field.bounding_box
        addr_center_x = (ax1 + ax2) / 2
        addr_center_y = (ay1 + ay2) / 2

    for block in blocks:
        match = re.search(r'\b([1-9][0-9]{5})\b', block.text)
        if match:
            dist = 999.0
            if addr_center_y is not None and addr_center_x is not None:
                dist = ((block.center[0] - addr_center_x) ** 2 + (block.center[1] - addr_center_y) ** 2) ** 0.5

            candidates.append(FieldCandidate(block.text, match.group(1), [block], "fallback", dist, block.ocr_confidence, True))

    if not candidates:
        return None

    candidates.sort(key=lambda c: c.sort_key(), reverse=True)
    best = candidates[0]

    return ExtractedField(
        value=best.normalized_value,
        ocr_confidence=best.ocr_confidence,
        anchor_matched=False,
        format_valid=True,
        composite_score=compute_composite_score(best.ocr_confidence, False, True),
        raw_text=best.raw_text,
        bounding_box=best.source_blocks[0].rect,
        source_page=source_page
    )