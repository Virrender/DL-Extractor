"""
Phase 1: Deterministic Aadhaar Card Extractor.

MVP limitations to revisit once tested against more real cards:
- Anchors are English-only. Hindi anchor text will not be recognized since
  the OCR engine is configured for lang="en". If Hindi-only labels prove
  common in your samples, look at a Hindi-capable PaddleOCR language model.
- Name extraction has no reliable "Name" label on most Aadhaar layouts, so
  it falls back to a positional heuristic anchored off Gender or the Aadhaar
  number (whichever was found), walking upward and skipping date/boilerplate
  lines. Validate against real samples and tighten if it misfires.
"""

import re
from typing import List, Optional, Literal

from app.schemas import (
    OCRBlock, ExtractedField,
    AadhaarFrontFields, AadhaarBackFields, AadhaarResponse
)
from app.services.common_extractors import (
    FieldCandidate, compute_composite_score, parse_calendar_date, parse_year_only,
    is_valid_name_part, extract_address, extract_pin_code, gate_by_confidence
)

AADHAAR_PATTERN = re.compile(r'([2-9]\d{3})\s?(\d{4})\s?(\d{4})')
GENDER_TOKENS = {"male": "MALE", "female": "FEMALE", "transgender": "TRANSGENDER"}


def _validate_aadhaar(text: str):
    m = AADHAAR_PATTERN.search(text)
    if m:
        return True, f"{m.group(1)}{m.group(2)}{m.group(3)}"
    return False, text


def _looks_like_date_or_boilerplate(text: str) -> bool:
    """Used by the name-extraction fallback to skip lines that are clearly not a name."""
    t = text.lower()
    if re.search(r'\d{1,2}\s*[-/.]\s*\d{1,2}\s*[-/.]\s*\d{4}', text):
        return True
    if re.search(r'\b(19|20)\d{2}\b', text):
        return True
    if any(k in t for k in [
        "dob", "birth", "government", "india", "unique identification",
        "male", "female", "transgender", "hoh", "head of household",
        "tehe", "mera aadhaar", "meri pehchan", "authority", "enrolment", "help@"
    ]):
        return True
    return False


class AadhaarExtractor:

    def extract(
        self,
        blocks: List[OCRBlock],
        pages_processed: Optional[List[Literal["front", "back"]]] = None
    ) -> AadhaarResponse:
        front_blocks = [b for b in blocks if b.page_source == "front"]
        back_blocks = [b for b in blocks if b.page_source == "back"]

        if not blocks:
            return AadhaarResponse(
                status="failed",
                missing_fields=["aadhaar_number", "name", "dob"],
                pages_processed=pages_processed if pages_processed is not None else [],
                warnings=["No OCR text blocks available for extraction."]
            )

        warnings: List[str] = []

        aadhaar_number = self._extract_aadhaar_number(front_blocks)
        if not aadhaar_number and back_blocks:
            # Fallback: Indian Aadhaar cards also print the 12-digit UID on the back
            aadhaar_number = self._extract_aadhaar_number(back_blocks)

        gender = self._extract_gender(front_blocks)
        dob = self._extract_dob(front_blocks)
        # Name extraction anchors off gender/aadhaar_number, NOT dob
        name = self._extract_name(front_blocks, gender_field=gender, aadhaar_field=aadhaar_number)

        address = extract_address(back_blocks, source_page="back")
        pin_code = extract_pin_code(back_blocks, address, source_page="back")

        aadhaar_number, w1 = gate_by_confidence(aadhaar_number)
        name, w2 = gate_by_confidence(name)
        dob, w3 = gate_by_confidence(dob)
        gender, w4 = gate_by_confidence(gender)
        address, w5 = gate_by_confidence(address)
        pin_code, w6 = gate_by_confidence(pin_code)
        warnings.extend(w for w in [w1, w2, w3, w4, w5, w6] if w)

        front_fields = AadhaarFrontFields(
            aadhaar_number=aadhaar_number, name=name, dob=dob, gender=gender
        )
        back_fields = AadhaarBackFields(address=address, pin_code=pin_code) if back_blocks else None

        missing = []
        if not aadhaar_number: missing.append("aadhaar_number")
        if not name: missing.append("name")
        if not dob: missing.append("dob")

        status: Literal["success", "partial", "failed"] = "success"
        if len(missing) == 3:
            status = "failed"
        elif len(missing) > 0:
            status = "partial"

        if pages_processed is not None:
            processed = pages_processed
        else:
            processed = []
            if front_blocks: processed.append("front")
            if back_blocks: processed.append("back")

        return AadhaarResponse(
            status=status,
            front=front_fields,
            back=back_fields,
            missing_fields=missing,
            pages_processed=processed,
            warnings=warnings
        )

    def _extract_aadhaar_number(self, blocks: List[OCRBlock]) -> Optional[ExtractedField]:
        candidates: List[FieldCandidate] = []
        anchors = ["aadhaar", "aadhar", "uidai", "vid"]

        # 1. Single block matching 12 digits
        for block in blocks:
            t = block.text.lower()
            val_ok, norm = _validate_aadhaar(block.text)
            if not val_ok:
                continue
            is_anchored = any(a in t for a in anchors)
            relation = "inline" if is_anchored else "fallback"
            candidates.append(FieldCandidate(block.text, norm, [block], relation, 0.0 if is_anchored else 999.0, block.ocr_confidence, True))

        # 2. Check for 3 horizontally adjacent 4-digit blocks (e.g. ['9756', '8503', '6053'])
        four_digit_blocks = [b for b in blocks if re.match(r'^\d{4}$', b.text.strip())]
        four_digit_blocks.sort(key=lambda b: (round(b.center[1] / 15.0), b.rect[0]))

        for i, b1 in enumerate(four_digit_blocks):
            for j in range(i + 1, len(four_digit_blocks)):
                b2 = four_digit_blocks[j]
                # Same horizontal line (y-center within 15px)
                if abs(b1.center[1] - b2.center[1]) > 15:
                    continue
                # Gap between b1 and b2 should be close (0 to 60px)
                gap1 = b2.rect[0] - b1.rect[2]
                if not (0 <= gap1 <= 60):
                    continue

                for k in range(j + 1, len(four_digit_blocks)):
                    b3 = four_digit_blocks[k]
                    if abs(b2.center[1] - b3.center[1]) > 15:
                        continue
                    gap2 = b3.rect[0] - b2.rect[2]
                    if not (0 <= gap2 <= 60):
                        continue

                    combined_text = f"{b1.text} {b2.text} {b3.text}"
                    val_ok, norm = _validate_aadhaar(combined_text)
                    if val_ok:
                        avg_conf = (b1.ocr_confidence + b2.ocr_confidence + b3.ocr_confidence) / 3.0
                        candidates.append(FieldCandidate(
                            combined_text, norm, [b1, b2, b3], "fallback", 100.0, avg_conf, True
                        ))

        if not candidates:
            return None

        candidates.sort(key=lambda c: c.sort_key(), reverse=True)
        best = candidates[0]

        bx = (
            min(b.rect[0] for b in best.source_blocks),
            min(b.rect[1] for b in best.source_blocks),
            max(b.rect[2] for b in best.source_blocks),
            max(b.rect[3] for b in best.source_blocks),
        )

        return ExtractedField(
            value=best.normalized_value,
            ocr_confidence=best.ocr_confidence,
            anchor_matched=(best.anchor_relation != "fallback"),
            format_valid=True,
            composite_score=compute_composite_score(best.ocr_confidence, best.anchor_relation != "fallback", True),
            raw_text=best.raw_text,
            bounding_box=bx,
            source_page=best.source_blocks[0].page_source
        )

    def _extract_dob(self, blocks: List[OCRBlock]) -> Optional[ExtractedField]:
        anchors_full = ["dob", "date of birth", "d.o.b", "d0b","birth"]
        anchors_year = ["year of birth", "yob"]
        candidates: List[FieldCandidate] = []

        for block in blocks:
            t = block.text.lower()
            matched_full = next((a for a in anchors_full if a in t), None)
            if matched_full:
                remainder = t.split(matched_full, 1)[1].strip(" :,-")
                if remainder:
                    val_ok, norm = parse_calendar_date(remainder)
                    if val_ok:
                        candidates.append(FieldCandidate(remainder, norm, [block], "inline", 0.0, block.ocr_confidence, True))
                continue

            matched_year = next((a for a in anchors_year if a in t), None)
            if matched_year:
                remainder = t.split(matched_year, 1)[1].strip(" :,-")
                if remainder:
                    val_ok, norm = parse_year_only(remainder)
                    if val_ok:
                        candidates.append(FieldCandidate(remainder, norm, [block], "inline", 0.0, block.ocr_confidence, True))

        if not candidates:
            for block in blocks:
                val_ok, norm = parse_calendar_date(block.text)
                if val_ok:
                    candidates.append(FieldCandidate(block.text, norm, [block], "fallback", 999.0, block.ocr_confidence, True))

        if not candidates:
            return None

        candidates.sort(key=lambda c: c.sort_key(), reverse=True)
        best = candidates[0]

        return ExtractedField(
            value=best.normalized_value,
            ocr_confidence=best.ocr_confidence,
            anchor_matched=(best.anchor_relation != "fallback"),
            format_valid=True,
            composite_score=compute_composite_score(best.ocr_confidence, best.anchor_relation != "fallback", True),
            raw_text=best.raw_text,
            bounding_box=best.source_blocks[0].rect,
            source_page="front"
        )

    def _extract_gender(self, blocks: List[OCRBlock]) -> Optional[ExtractedField]:
        candidates: List[FieldCandidate] = []
        for block in blocks:
            t = block.text.lower()
            # Use substring matching to ignore hallucinated regional prefixes
            if "female" in t:
                candidates.append(FieldCandidate(block.text, "FEMALE", [block], "inline", 0.0, block.ocr_confidence, True))
            elif "male" in t: # Must use elif so "female" doesn't falsely trigger "male"
                candidates.append(FieldCandidate(block.text, "MALE", [block], "inline", 0.0, block.ocr_confidence, True))
            elif "transgender" in t:
                candidates.append(FieldCandidate(block.text, "TRANSGENDER", [block], "inline", 0.0, block.ocr_confidence, True))

        if not candidates:
            return None

        candidates.sort(key=lambda c: c.sort_key(), reverse=True)
        best = candidates[0]

        return ExtractedField(
            value=best.normalized_value,
            ocr_confidence=best.ocr_confidence,
            anchor_matched=True,
            format_valid=True,
            composite_score=compute_composite_score(best.ocr_confidence, True, True),
            raw_text=best.raw_text,
            bounding_box=best.source_blocks[0].rect,
            source_page="front"
        )

    def _extract_name(
        self,
        blocks: List[OCRBlock],
        gender_field: Optional[ExtractedField] = None,
        aadhaar_field: Optional[ExtractedField] = None
    ) -> Optional[ExtractedField]:
        """
        Preferred: explicit 'Name' anchor if the layout has one.
        Fallback: walk upward from whichever of {gender, aadhaar number} was
        found, skipping date/boilerplate lines, and take the first plausible
        Latin-script name line. Independent of DOB — previously this only ran
        if DOB had already been found, which meant a DOB miss also broke name
        extraction.
        """
        candidates: List[FieldCandidate] = []

        for block in blocks:
            t = block.text.lower()
            if "name" in t and "father" not in t and "husband" not in t:
                remainder = t.split("name", 1)[1].strip(" :,-")
                if remainder and is_valid_name_part(remainder):
                    candidates.append(FieldCandidate(remainder, remainder.upper(), [block], "inline", 0.0, block.ocr_confidence, True))

        if candidates:
            candidates.sort(key=lambda c: c.sort_key(), reverse=True)
            best = candidates[0]
            return ExtractedField(
                value=best.normalized_value,
                ocr_confidence=best.ocr_confidence,
                anchor_matched=True,
                format_valid=True,
                composite_score=compute_composite_score(best.ocr_confidence, True, True),
                raw_text=best.raw_text,
                bounding_box=best.source_blocks[0].rect,
                source_page="front"
            )

        ref_field = gender_field or aadhaar_field
        if not ref_field or not ref_field.bounding_box:
            return None

        rx1, ry1, rx2, ry2 = ref_field.bounding_box

        above = [
            b for b in blocks
            if b.rect[3] <= ry1 and (ry1 - b.rect[3]) <= 400
            and max(b.rect[0], rx1) <= (min(b.rect[2], rx2) + 150.0)  # loose column overlap
        ]

        candidate_blocks = []
        for b in above:
            if _looks_like_date_or_boilerplate(b.text):
                continue
            if is_valid_name_part(b.text):
                candidate_blocks.append(b)

        if not candidate_blocks:
            return None

        def _score_name_block(b: OCRBlock) -> float:
            words = b.text.strip().split()
            score = 0.0
            if len(words) >= 2:
                score += 20.0  # Real names typically have 2+ words (e.g. 'Virender Kumar')
            elif len(words) == 1 and len(words[0]) >= 4:
                score += 5.0
            else:
                score -= 15.0

            # Proximity bonus (closer to DOB/Gender is better)
            dist = ry1 - b.rect[3]
            score += max(0.0, 10.0 - (dist / 30.0))
            score += b.ocr_confidence * 5.0
            return score

        candidate_blocks.sort(key=_score_name_block, reverse=True)
        best_block = candidate_blocks[0]

        return ExtractedField(
            value=best_block.text.strip().upper(),
            ocr_confidence=best_block.ocr_confidence,
            anchor_matched=False,
            format_valid=True,
            composite_score=compute_composite_score(best_block.ocr_confidence, False, True),
            raw_text=best_block.text,
            bounding_box=best_block.rect,
            source_page="front"
        )