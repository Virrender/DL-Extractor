import sys
from PIL import Image
from app.services.file_handler import NormalizedPage
from app.services.ocr_engine import PaddleOCREngine

def run_debug(image_path):
    print(f"--- Loading image: {image_path} ---")
    img = Image.open(image_path).convert("RGB")
    
    # Mock a NormalizedPage just like the file handler does
    page = NormalizedPage(
        original_image=img, 
        working_image=img, 
        page_source="front",
        page_index=0, 
        original_width=img.width, 
        original_height=img.height,
        working_width=img.width, 
        working_height=img.height, 
        scale_factor=1.0
    )
    
    engine = PaddleOCREngine()
    
    # Run the engine (this triggers the internal orientation/skew passes)
    result = engine.process_page(page)
    
    # Handle the tuple return type (Blocks, CorrectedImage)
    if isinstance(result, tuple) and len(result) == 2:
        blocks, corrected_img = result
        # Save the corrected image so you can literally see what PaddleOCR saw
        corrected_img.save("debug_corrected_image.jpg")
        print("\n[INFO] Saved 'debug_corrected_image.jpg' to your backend folder.")
        print("[INFO] Open this image to see how blurry the text got after rotation!\n")
    else:
        blocks = result
        print("\n[WARNING] Could not save corrected image (process_page did not return a tuple).\n")

    print("--- RAW OCR BLOCKS ---")
    for b in blocks:
        print(f"Text: '{b.text}' | Conf: {b.ocr_confidence:.2f} | Rect: {b.rect}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_rotated_ocr.py <path_to_image>")
    else:
        run_debug(sys.argv[1])