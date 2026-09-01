from paddleocr import PaddleOCR

ocr=PaddleOCR(lang="en")


def extract_text(image_path):
    result=ocr.predict(image_path)

    extracted_data=[
    ]

    for res in result:
        texts=res["rec_texts"]
        scores=res["rec_scores"]
        boxes=res["rec_boxes"]

        for text, score, box in zip(texts,scores,boxes):
            extracted_data.append(
                {
                    "text":text,
                    "confidence":float(score),
                    "box":box.tolist(),
                }
            )
    return extracted_data