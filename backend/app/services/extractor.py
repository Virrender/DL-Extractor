import math
import re
from difflib import SequenceMatcher


DATE_PATTERN = r"\d{2}[-/.]\d{2}[-/.]\d{4}"
BLOOD_GROUP_PATTERN = r"(A|B|AB|O)[+-]"
DL_NUMBER_PATTERN = r"HP[A-Z0-9]{8,15}"

LABEL_THRESHOLD = 0.7


def normalize_text(text):
    text = text.lower()
    text = text.strip()
    text = re.sub(r"\s+", " ", text)

    return text


def text_similarity(text1, text2):
    return SequenceMatcher(
        None,
        normalize_text(text1),
        normalize_text(text2)
    ).ratio()


def get_center(box):
    x1, y1, x2, y2 = box

    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2

    return center_x, center_y


def is_below(label_box, candidate_box):
    _, label_y = get_center(label_box)
    _, candidate_y = get_center(candidate_box)

    return candidate_y > label_y


def is_horizontally_aligned(
    label_box,
    candidate_box,
    threshold=100
):
    label_x, _ = get_center(label_box)
    candidate_x, _ = get_center(candidate_box)

    return abs(candidate_x - label_x) <= threshold


def distance(box1, box2):
    x1, y1 = get_center(box1)
    x2, y2 = get_center(box2)

    return math.sqrt(
        (x2 - x1) ** 2 +
        (y2 - y1) ** 2
    )


def find_label(ocr_data, expected_label):
    best_match = None
    best_similarity = 0

    for item in ocr_data:
        similarity = text_similarity(
            item["text"],
            expected_label
        )

        if similarity >= LABEL_THRESHOLD and similarity > best_similarity:
            best_match = item
            best_similarity = similarity

    return best_match


def find_dob_candidate(ocr_data):
    dob_label = find_label(
        ocr_data,
        "date of birth"
    )

    if dob_label is None:
        return None

    candidates = []

    for item in ocr_data:
        text = item["text"].strip()

        if not re.fullmatch(DATE_PATTERN, text):
            continue

        if not is_below(
            dob_label["box"],
            item["box"]
        ):
            continue

        if not is_horizontally_aligned(
            dob_label["box"],
            item["box"],
            threshold=150
        ):
            continue

        candidates.append(
            (
                distance(
                    dob_label["box"],
                    item["box"]
                ),
                item
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda candidate: candidate[0]
    )

    return candidates[0][1]["text"].strip()


def find_blood_group_candidate(ocr_data):
    blood_group_label = find_label(
        ocr_data,
        "blood group"
    )

    candidates = []

    for item in ocr_data:
        text = item["text"].strip().upper()

        if not re.fullmatch(
            BLOOD_GROUP_PATTERN,
            text
        ):
            continue

        if blood_group_label is not None:
            if not is_below(
                blood_group_label["box"],
                item["box"]
            ):
                continue

            if not is_horizontally_aligned(
                blood_group_label["box"],
                item["box"],
                threshold=150
            ):
                continue

        candidates.append(item)

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item["confidence"],
        reverse=True
    )

    return candidates[0]["text"].strip().upper()


def find_name_candidate(ocr_data):
    name_label = find_label(
        ocr_data,
        "name"
    )

    if name_label is None:
        return None

    candidates = []

    for item in ocr_data:
        if item is name_label:
            continue

        text = item["text"].strip()

        if not text:
            continue

        if re.fullmatch(DATE_PATTERN, text):
            continue

        if re.fullmatch(
            BLOOD_GROUP_PATTERN,
            text.upper()
        ):
            continue

        if text_similarity(text, "father") >= LABEL_THRESHOLD:
            continue

        if text_similarity(text, "name") >= LABEL_THRESHOLD:
            continue

        # Name value is normally close to the Name label.
        candidate_distance = distance(
            name_label["box"],
            item["box"]
        )

        candidates.append(
            (
                candidate_distance,
                item
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda candidate: candidate[0]
    )

    return candidates[0][1]["text"].strip()


def find_father_name_candidate(ocr_data):
    father_label = find_label(
        ocr_data,
        "father"
    )

    if father_label is None:
        return None

    candidates = []

    for item in ocr_data:
        if item is father_label:
            continue

        text = item["text"].strip()

        if not text:
            continue

        if re.fullmatch(DATE_PATTERN, text):
            continue

        if re.fullmatch(
            BLOOD_GROUP_PATTERN,
            text.upper()
        ):
            continue

        if text_similarity(
            text,
            "name"
        ) >= LABEL_THRESHOLD:
            continue

        if not is_below(
            father_label["box"],
            item["box"]
        ):
            continue

        if not is_horizontally_aligned(
            father_label["box"],
            item["box"],
            threshold=100
        ):
            continue

        candidates.append(
            (
                distance(
                    father_label["box"],
                    item["box"]
                ),
                item
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda candidate: candidate[0]
    )

    return candidates[0][1]["text"].strip()


def find_dl_number_candidate(ocr_data):
    candidates = []

    for item in ocr_data:
        text = item["text"].strip().upper()

        cleaned_text = re.sub(
            r"[^A-Z0-9]",
            "",
            text
        )

        if not cleaned_text.startswith("HP"):
            continue

        if not re.fullmatch(
            DL_NUMBER_PATTERN,
            cleaned_text
        ):
            continue

        candidates.append(item)

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item["confidence"],
        reverse=True
    )

    return re.sub(
        r"[^A-Z0-9]",
        "",
        candidates[0]["text"].strip().upper()
    )


def find_date_near_label(
    ocr_data,
    label_text
):
    label = find_label(
        ocr_data,
        label_text
    )

    if label is None:
        return None

    candidates = []

    for item in ocr_data:
        text = item["text"].strip()

        if not re.fullmatch(
            DATE_PATTERN,
            text
        ):
            continue

        if not is_below(
            label["box"],
            item["box"]
        ):
            continue

        if not is_horizontally_aligned(
            label["box"],
            item["box"],
            threshold=150
        ):
            continue

        candidates.append(
            (
                distance(
                    label["box"],
                    item["box"]
                ),
                item
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda candidate: candidate[0]
    )

    return candidates[0][1]["text"].strip()


def find_issue_date_candidate(ocr_data):
    return find_date_near_label(
        ocr_data,
        "date of issue"
    )


def find_validity_candidate(ocr_data):
    return find_date_near_label(
        ocr_data,
        "validity"
    )


def extract_fields(ocr_data):
    return {
        "dl_number": find_dl_number_candidate(ocr_data),
        "date_of_issue": find_issue_date_candidate(ocr_data),
        "validity": find_validity_candidate(ocr_data),
        "date_of_birth": find_dob_candidate(ocr_data),
        "blood_group": find_blood_group_candidate(ocr_data),
        "name": find_name_candidate(ocr_data),
        "father_name": find_father_name_candidate(ocr_data),
    }