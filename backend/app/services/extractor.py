import re
import math
from difflib import SequenceMatcher
DATE_PATTERN=r"\d{2}[-/.]\d{2}[-/.]\d{4}"

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

DOB_LABEL = "date of birth"
DOB_LABEL_THRESHOLD = 0.5

def is_dob_label(text):
    similarity = text_similarity(text, DOB_LABEL)

    return similarity >= DOB_LABEL_THRESHOLD

# def extract_dob(ocr_data):
#     for i, item in enumerate(ocr_data):
#         text=item["text"].strip().lower()

#         print(f"CHECKING: {repr(text)}")

#         if text=="date of birth":
            
#             for next_item in ocr_data[i+1:]:
#                 value=next_item["text"].strip()
#                 if re.fullmatch(DATE_PATTERN,value):
#                     return value

#     return None

# def inspect_dates(ocr_data):
#     dob_label_box = None

#     date_candidates = []

#     for item in ocr_data:
#         text = item["text"].strip()

#         if text.lower() == "date of birth":
#             dob_label_box = item["box"]

#         if re.fullmatch(DATE_PATTERN, text):
#             date_candidates.append(item)

#     if dob_label_box is None:
#         print("DOB label not found")
#         return

#     print("DOB LABEL BOX:", dob_label_box)

#     for candidate in date_candidates:
#         text = candidate["text"]
#         box = candidate["box"]

#         print(
#             f"\nCandidate: {text}"
#             f"\nBox: {box}"
#             f"\nBelow: {is_below(dob_label_box, box)}"
#             f"\nAligned: {is_horizontally_aligned(dob_label_box, box)}"
#             f"\nBelow + Aligned: {is_below_and_aligned(dob_label_box, box)}"
#         )



def get_center(box):
    x1,y1,x2,y2=box
    center_x=(x1+x2)/2
    center_y=(y1+y2)/2

    return center_x, center_y

def is_below(label_box, candidate_box):
    label_x, label_y = get_center(label_box)
    candidate_x, candidate_y = get_center(candidate_box)

    return candidate_y > label_y


def is_horizontally_aligned(label_box, candidate_box, threshold=50):
    label_x, _ = get_center(label_box)
    candidate_x, _ = get_center(candidate_box)

    return abs(candidate_x - label_x) <= threshold

def is_below_and_aligned(label_box, candidate_box):
    return (
        is_below(label_box, candidate_box)
        and is_horizontally_aligned(label_box, candidate_box)
    )

def distance(box1,box2):
    x1,y1=get_center(box1)
    x2,y2=get_center(box2)

    return math.sqrt((x2-x1)**2 + (y2-y1)**2)


def find_dob_candidate(ocr_data):
    dob_label_box = None
    date_candidates = []

    for item in ocr_data:
        text = item["text"].strip()

        if is_dob_label(text):
            dob_label_box = item["box"]

        if re.fullmatch(DATE_PATTERN, text):
            date_candidates.append(item)

    if dob_label_box is None:
        return None

    valid_candidates = []

    for candidate in date_candidates:
        if is_horizontally_aligned(
            dob_label_box,
            candidate["box"]
        ):
            candidate_distance = distance(
                dob_label_box,
                candidate["box"]
            )

            valid_candidates.append(
                (
                    candidate_distance,
                    candidate["text"]
                )
            )

    if not valid_candidates:
        return None

    valid_candidates.sort()

    return valid_candidates[0][1]



# box1 = [100, 100, 200, 130]
# box2 = [100, 150, 200, 180]

# print(distance(box1, box2))