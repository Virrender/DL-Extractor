import re
from difflib import SequenceMatcher


PINCODE_PATTERN = r"\b\d{6}\b"

ADDRESS_LABEL = "present address"
LABEL_THRESHOLD = 0.65


def normalize_text(text):
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)

    return text


def text_similarity(text1, text2):
    return SequenceMatcher(
        None,
        normalize_text(text1),
        normalize_text(text2)
    ).ratio()


def find_address_label(ocr_data):
    best_match = None
    best_similarity = 0

    for item in ocr_data:
        similarity = text_similarity(
            item["text"],
            ADDRESS_LABEL
        )

        if (
            similarity >= LABEL_THRESHOLD
            and similarity > best_similarity
        ):
            best_match = item
            best_similarity = similarity

    return best_match


def get_center(box):
    x1, y1, x2, y2 = box

    return (
        (x1 + x2) / 2,
        (y1 + y2) / 2
    )


def is_below(label_box, candidate_box):
    _, label_y = get_center(label_box)
    _, candidate_y = get_center(candidate_box)

    return candidate_y > label_y


def horizontal_overlap(box1, box2):
    x1_a, _, x2_a, _ = box1
    x1_b, _, x2_b, _ = box2

    return max(
        0,
        min(x2_a, x2_b) - max(x1_a, x1_b)
    )


def is_address_candidate(label_box, candidate_box):
    if not is_below(label_box, candidate_box):
        return False

    label_x1, _, label_x2, _ = label_box
    candidate_x1, _, candidate_x2, _ = candidate_box

    overlap = horizontal_overlap(
        label_box,
        candidate_box
    )

    label_width = label_x2 - label_x1

    # Candidate should overlap the address label's
    # horizontal region.
    if overlap > 0:
        return True

    # Also allow text extending somewhat to the right.
    if (
        candidate_x1 >= label_x1 - 50
        and candidate_x1 <= label_x2 + 100
    ):
        return True

    return False


def find_address_lines(ocr_data):
    label = find_address_label(ocr_data)

    if label is None:
        return []

    candidates = []

    for item in ocr_data:

        if item is label:
            continue

        text = item["text"].strip()

        if not text:
            continue

        if not is_address_candidate(
            label["box"],
            item["box"]
        ):
            continue

        candidates.append(item)

    candidates.sort(
        key=lambda item: (
            get_center(item["box"])[1],
            get_center(item["box"])[0]
        )
    )

    return candidates


def extract_pincode(text):
    match = re.search(
        PINCODE_PATTERN,
        text
    )

    if match:
        return match.group()

    return None


def parse_address(address_text):
    pincode = extract_pincode(address_text)

    cleaned = address_text

    if pincode:
        cleaned = re.sub(
            PINCODE_PATTERN,
            "",
            cleaned
        )

    cleaned = re.sub(
        r"\s*,\s*",
        ", ",
        cleaned
    )

    parts = [
        part.strip()
        for part in cleaned.split(",")
        if part.strip()
    ]

    result = {
        "raw": address_text,
        "village": None,
        "post_office": None,
        "district": None,
        "state": None,
        "pincode": pincode
    }

    if parts:
        first_part = parts[0]

        village_match = re.search(
            r"(?:VILL|VILLAGE)\s+(.+)",
            first_part,
            re.IGNORECASE
        )

        if village_match:
            result["village"] = village_match.group(1).strip()
        else:
            result["village"] = first_part

    if len(parts) >= 2:
        second_part = parts[1]

        po_match = re.search(
            r"(?:PO|P\.O\.|POST OFFICE)\s+(.+)",
            second_part,
            re.IGNORECASE
        )

        if po_match:
            result["post_office"] = po_match.group(1).strip()
        else:
            result["post_office"] = second_part

    if len(parts) >= 3:
        result["district"] = parts[2]

    if len(parts) >= 4:
        result["state"] = parts[3]

    return result


def extract_address(ocr_data):
    address_lines = find_address_lines(
        ocr_data
    )

    if not address_lines:
        return None

    texts = [
        item["text"].strip()
        for item in address_lines
    ]

    address_text = " ".join(texts)

    # Stop at obvious unrelated fields.
    address_text = re.split(
        r"\b(?:mobile|endorsement|signature)\b",
        address_text,
        flags=re.IGNORECASE
    )[0].strip()

    if not address_text:
        return None

    return parse_address(address_text)