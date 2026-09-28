import io
import sys
from fastapi.testclient import TestClient
from app.main import app

def run_tests():
    client = TestClient(app)
    print("--- Starting Backend Tests ---")

    # Test 1: DL QR payload
    res1 = client.post(
        "/api/v1/extract/qr-payload",
        json={"raw_payload": "DL NO: MH1220110069564\nDOB: 15/05/1988\nName: RAJESH KUMAR"}
    )
    print("Test 1 (DL QR):", res1.status_code)
    assert res1.status_code == 200, f"Failed: {res1.text}"
    data1 = res1.json()
    assert data1["document_type"] == "driving_licence"
    assert data1["result"]["front"]["id_number"]["value"] == "MH1220110069564"
    print("  -> DL QR extracted:", data1["result"]["front"]["id_number"]["value"])

    # Test 2: Aadhaar XML QR payload
    xml_payload = '<PrintLetterBarcodeData uid="987654321012" name="PRIYA SHARMA" gender="F" yob="1995" dob="12/04/1995" pc="110001" state="DELHI"/>'
    res2 = client.post(
        "/api/v1/extract/qr-payload",
        json={"raw_payload": xml_payload}
    )
    print("Test 2 (Aadhaar XML QR):", res2.status_code)
    assert res2.status_code == 200, f"Failed: {res2.text}"
    data2 = res2.json()
    assert data2["document_type"] == "aadhaar_card"
    assert data2["result"]["front"]["name"]["value"] == "PRIYA SHARMA"
    assert data2["result"]["front"]["aadhaar_number"]["value"] == "987654321012"
    print("  -> Aadhaar XML QR extracted:", data2["result"]["front"]["name"]["value"])

    # Test 3: Upload with front image only
    with open("app/test_img_DL/DL.jpg", "rb") as f:
        res3 = client.post("/api/v1/extract", files={"front_image": ("DL.jpg", f, "image/jpeg")})
    print("Test 3 (Front image only):", res3.status_code)
    assert res3.status_code == 200, f"Failed: {res3.text}"
    print("  -> Doc type:", res3.json()["document_type"])

    # Test 4: Upload with empty back_image string
    with open("app/test_img_DL/DL.jpg", "rb") as f:
        res4 = client.post("/api/v1/extract", files={"front_image": ("DL.jpg", f, "image/jpeg")}, data={"back_image": ""})
    print("Test 4 (Empty back_image string):", res4.status_code)
    assert res4.status_code == 200, f"Failed: {res4.text}"

    # Test 5: Upload with empty back_image file part
    with open("app/test_img_DL/DL.jpg", "rb") as f:
        res5 = client.post(
            "/api/v1/extract",
            files={
                "front_image": ("DL.jpg", f, "image/jpeg"),
                "back_image": ("", io.BytesIO(b""), "application/octet-stream")
            }
        )
    print("Test 5 (Empty back_image file part):", res5.status_code)
    assert res5.status_code == 200, f"Failed: {res5.text}"

    # Test 6: Aadhaar Secure QR (Base10 integer string)
    import zlib
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="purple").save(buf, format="JPEG")
    fields = ["V2", "0", "3081/12345/6789", "VIRRENDER SINGH", "15-08-1998", "M", "S/O RAM SINGH", "CHAMBA", "NEAR TEMPLE", "H NO 42", "VILLAGE", "176324", "BADGRAM", "HIMACHAL PRADESH", "MAIN ROAD", "BHARMOUR", "BADGRAM", "8788"]
    raw_bytes = bytearray()
    for item in fields:
        raw_bytes.extend(item.encode("ISO-8859-1"))
        raw_bytes.append(255)
    raw_bytes.extend(buf.getvalue())
    raw_bytes.extend(b"\x00" * 256)
    co = zlib.compressobj(wbits=16 + zlib.MAX_WBITS)
    compressed = co.compress(bytes(raw_bytes)) + co.flush()
    base10_str = str(int.from_bytes(compressed, byteorder="big"))

    res6 = client.post("/api/v1/extract/qr-payload", json={"raw_payload": base10_str})
    print("Test 6 (Aadhaar Secure QR Base10):", res6.status_code)
    assert res6.status_code == 200, f"Failed: {res6.text}"
    data6 = res6.json()
    assert data6["document_type"] == "aadhaar_card"
    assert data6["result"]["front"]["name"]["value"] == "VIRRENDER SINGH"
    assert data6["result"]["front"]["aadhaar_number"]["value"] == "XXXX XXXX 3081"
    assert data6["photo_base64"] is not None
    print("  -> Aadhaar Base10 QR extracted:", data6["result"]["front"]["name"]["value"], data6["result"]["front"]["aadhaar_number"]["value"])

    # Test 7: Aadhaar Secure QR (Latin1 raw binary string)
    latin1_str = compressed.decode("latin1")
    res7 = client.post("/api/v1/extract/qr-payload", json={"raw_payload": latin1_str})
    print("Test 7 (Aadhaar Secure QR Latin1):", res7.status_code)
    assert res7.status_code == 200, f"Failed: {res7.text}"
    data7 = res7.json()
    assert data7["document_type"] == "aadhaar_card"
    assert data7["result"]["front"]["name"]["value"] == "VIRRENDER SINGH"
    assert data7["photo_base64"] is not None
    print("  -> Aadhaar Latin1 QR extracted:", data7["result"]["front"]["name"]["value"], "Photo present:", bool(data7["photo_base64"]))

    print("\nALL 7 BACKEND TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
