from services.ocr import extract_text
from services.extractor import   find_dob_candidate
images=[
        "backend/app/test_img/dl1left_tilted.jpg",
        "backend/app/test_img/dl2slant_front.jpg",
        "backend/app/test_img/dl3top_view.jpg",
        "backend/app/test_img/dl4perfect_cropped.jpg",
        "backend/app/test_img/dl5left_face.jpg",
        "backend/app/test_img/dl6right_face.jpg",
        "backend/app/test_img/dl7back_face.jpg"
           ]

for image in images:
    print(f"\n=====>{image}")
    ocr_data=extract_text(image)



    # for i, item in enumerate(ocr_data):
    #     print(
    #         i,
    #         f"{item['text']!r:25}"
    #         f"box={item['box']}"
    #     )

    # for item in ocr_data:
    #     print(item)
    
    dob = find_dob_candidate(ocr_data)
    print("DOB:", dob)
    
    


# data=extract_text(image_path)
# for item in data:
#     print(item)