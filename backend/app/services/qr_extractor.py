"""
QR Code Detection and Parsing.

Handles two document types with fundamentally different QR realities:

- Aadhaar Secure QR: a well-defined, deterministic format -- a purely
  numeric string that decompresses (zlib) into pipe-delimited demographic
  fields. Cannot supply the full Aadhaar number by design (UIDAI masks it
  in the QR for privacy) -- only name/dob/gender/address/reference id.
- Driving Licence QR: no single national standard across Indian states/RTOs.
  This is a best-effort parser: looks for a DL-number-shaped token and a
  date-shaped token in whatever raw text the QR decodes to. A URL-only
  payload is returned as-is (verification_url) rather than auto-fetched,
  since that would mean this backend making outbound calls to arbitrary
  third-party/government endpoints on every scan.
"""

import base64
import io
import logging
import re
import zlib
from typing import Any, Dict, Optional

import numpy as np
from PIL import Image

try:
    from pyzbar import pyzbar
    _HAS_PYZBAR = True
except Exception:
    _HAS_PYZBAR = False
    import cv2

logger = logging.getLogger(__name__)

if not _HAS_PYZBAR:
    logger.warning(
        "pyzbar not available; falling back to OpenCV QRCodeDetector. "
        "Dense Aadhaar Secure QR codes may not decode reliably. "
        "Install pyzbar + libzbar (Windows: choco install zbar) for better hit-rate."
    )


def detect_and_decode_qr(img: Image.Image) -> Optional[str]:
    """Detects and decodes a single QR code in the given image. Returns the
    raw decoded string payload, or None if no QR was found/decoded."""
    if _HAS_PYZBAR:
        results = pyzbar.decode(img)
        if results:
            try:
                return results[0].data.decode("utf-8", errors="ignore")
            except Exception as e:
                logger.info(f"QR decode (pyzbar) failed to decode bytes: {e}")
                return None
        return None
    else:
        arr = np.array(img.convert("RGB"))
        detector = cv2.QRCodeDetector()
        data, points, _ = detector.detectAndDecode(arr)
        return data if data else None


import json
import xml.etree.ElementTree as ET

# ============================================================================
# Aadhaar QR parsing (Secure numeric zlib + Standard XML QR)
# ============================================================================

FIELD_ORDER = [
    "email_mobile_flag", "reference_id", "name", "dob", "gender",
    "care_of", "district", "landmark", "house", "location",
    "pincode", "post_office", "state", "street", "sub_district"
]


def parse_aadhaar_xml_qr(raw_payload: str) -> Optional[Dict[str, Any]]:
    """Parses standard/older Aadhaar XML QR format: <PrintLetterBarcodeData .../>"""
    if "<PrintLetterBarcodeData" not in raw_payload:
        return None
    try:
        start = raw_payload.find("<PrintLetterBarcodeData")
        end = raw_payload.find("/>", start)
        if end != -1:
            xml_str = raw_payload[start:end + 2]
        else:
            xml_str = raw_payload[start:]
            if not xml_str.endswith(">"):
                xml_str += "/>"

        root = ET.fromstring(xml_str)
        attrs = root.attrib
        fields: Dict[str, Any] = {
            "name": attrs.get("name"),
            "dob": attrs.get("dob") or attrs.get("yob"),
            "gender": attrs.get("gender"),
            "aadhaar_number": attrs.get("uid"),
            "care_of": attrs.get("co"),
            "house": attrs.get("house"),
            "street": attrs.get("street"),
            "landmark": attrs.get("lm"),
            "location": attrs.get("loc"),
            "vtc": attrs.get("vtc"),
            "post_office": attrs.get("po"),
            "district": attrs.get("dist"),
            "sub_district": attrs.get("subdist"),
            "state": attrs.get("state"),
            "pincode": attrs.get("pc"),
        }
        cleaned = {k: v.strip() for k, v in fields.items() if v}
        return cleaned if cleaned else None
    except Exception as e:
        logger.info(f"Aadhaar XML QR parsing failed: {e}")
        return None


def parse_aadhaar_secure_qr(raw_payload: str) -> Optional[Dict[str, Any]]:
    """
    Attempts to parse a decoded Aadhaar Secure QR payload.
    Supports both V1 and V2 (2022+) specifications, Gzip/Deflate compression,
    and multiple payload encodings (numeric base-10, latin1 bytes, raw chars, base64).
    Crucially avoids raw string stripping which corrupts binary compressed streams.
    """
    if not raw_payload:
        return None

    raw_clean = raw_payload.strip()

    # 1. Try pyaadhaar if available and payload is numeric
    if raw_clean.isdigit():
        try:
            from pyaadhaar.decode import AadhaarSecureQr
            obj = AadhaarSecureQr(int(raw_clean))
            data = obj.decodeddata()
            if data and data.get("name"):
                fields = {
                    "name": data.get("name"),
                    "dob": data.get("dob"),
                    "gender": data.get("gender"),
                    "reference_id": data.get("referenceid") or data.get("reference_id"),
                    "care_of": data.get("careof"),
                    "house": data.get("house"),
                    "street": data.get("street"),
                    "landmark": data.get("landmark"),
                    "location": data.get("location"),
                    "vtc": data.get("vtc"),
                    "post_office": data.get("postoffice"),
                    "district": data.get("district"),
                    "sub_district": data.get("subdistrict"),
                    "state": data.get("state"),
                    "pincode": data.get("pincode"),
                }
                ref = fields.get("reference_id")
                if ref and len(str(ref)) >= 4 and str(ref)[:4].isdigit():
                    fields["aadhaar_number"] = f"XXXX XXXX {str(ref)[:4]}"
                # Extract photo if present in QR code
                try:
                    if hasattr(obj, 'isImage') and obj.isImage():
                        img = obj.image()
                        if img:
                            buf = io.BytesIO()
                            img.convert("RGB").save(buf, format="JPEG")
                            fields["_photo_b64"] = base64.b64encode(buf.getvalue()).decode("ascii")
                except Exception as e:
                    logger.debug(f"pyaadhaar image extraction note: {e}")
                cleaned = {k: v.strip() if isinstance(v, str) else v for k, v in fields.items() if v}
                if cleaned.get("name"):
                    logger.info("Aadhaar Secure QR successfully parsed via pyaadhaar")
                    return cleaned
        except Exception as e:
            logger.info(f"pyaadhaar attempt note: {e}")

    # 2. Build candidate byte streams without corrupting binary data with strip()
    candidates_bytes = []

    # Format A: Decimal string (base-10 encoded integer)
    if raw_clean.isdigit():
        try:
            n = int(raw_clean)
            b1 = n.to_bytes((n.bit_length() + 7) // 8, byteorder="big").lstrip(b'\x00')
            candidates_bytes.append(b1)
            b2 = n.to_bytes(5000, byteorder="big").lstrip(b'\x00')
            candidates_bytes.append(b2)
        except Exception:
            pass

    # Format B: Raw byte representations (MUST preserve both unstripped and stripped variants)
    for r in (raw_payload, raw_clean):
        try:
            candidates_bytes.append(bytes([ord(c) & 0xFF for c in r]))
        except Exception:
            pass
        try:
            candidates_bytes.append(r.encode("latin1", errors="ignore"))
        except Exception:
            pass
        try:
            candidates_bytes.append(r.encode("utf-8", errors="ignore"))
        except Exception:
            pass
        try:
            candidates_bytes.append(base64.b64decode(r))
        except Exception:
            pass

    # 3. Try decompression across all window bits (31 = Gzip, 15/-15 = zlib/raw deflate)
    decompressed = None
    wbits_to_try = (31, 16 + zlib.MAX_WBITS, -15, 15, zlib.MAX_WBITS, -zlib.MAX_WBITS)

    for b in candidates_bytes:
        if not b or len(b) < 10:
            continue
        for wb in wbits_to_try:
            try:
                dec = zlib.decompress(b, wb)
                if dec and len(dec) > 20:
                    decompressed = dec
                    break
            except Exception:
                continue
        if decompressed:
            break

    if not decompressed:
        logger.info("Aadhaar QR payload could not be decompressed.")
        return None

    # 4. Parse decompressed byte stream
    try:
        is_v2 = False
        try:
            if decompressed[:2].decode("ISO-8859-1", errors="ignore") == "V2":
                is_v2 = True
        except Exception:
            pass

        if is_v2:
            field_order = [
                "version", "email_mobile_flag", "reference_id", "name", "dob", "gender",
                "care_of", "district", "landmark", "house", "location", "pincode",
                "post_office", "state", "street", "sub_district", "vtc", "last_4_digits_mobile_no"
            ]
        else:
            field_order = [
                "email_mobile_flag", "reference_id", "name", "dob", "gender",
                "care_of", "district", "landmark", "house", "location", "pincode",
                "post_office", "state", "street", "sub_district", "vtc"
            ]

        # Locate delimiters (byte 255 / 0xFF)
        delimiters = [-1]
        for idx, byte_val in enumerate(decompressed):
            if byte_val == 255:
                delimiters.append(idx)
                if len(delimiters) > len(field_order):
                    break

        fields: Dict[str, Any] = {}
        for i, name in enumerate(field_order):
            if i + 1 < len(delimiters):
                part = decompressed[delimiters[i] + 1 : delimiters[i + 1]]
                try:
                    val = part.decode("ISO-8859-1", errors="ignore").strip()
                    fields[name] = val if val else None
                except Exception:
                    fields[name] = None

        # Check for cardholder photo stream after demographic delimiters
        jpeg_idx = decompressed.find(b'\xff\xd8')
        if jpeg_idx != -1:
            jpeg_end = decompressed.find(b'\xff\xd9', jpeg_idx)
            if jpeg_end != -1:
                jpeg_bytes = decompressed[jpeg_idx : jpeg_end + 2]
            else:
                jpeg_bytes = decompressed[jpeg_idx : len(decompressed) - 256]
            try:
                img = Image.open(io.BytesIO(jpeg_bytes))
                buf = io.BytesIO()
                img.convert("RGB").save(buf, format="JPEG")
                fields["_photo_b64"] = base64.b64encode(buf.getvalue()).decode("ascii")
            except Exception as e:
                logger.debug(f"Photo processing note: {e}")
                fields["_photo_b64"] = base64.b64encode(jpeg_bytes).decode("ascii")

        # Fallback last 4 digits of Aadhaar from reference_id (e.g. "3081/...")
        ref = fields.get("reference_id")
        if ref and len(str(ref)) >= 4 and str(ref)[:4].isdigit():
            fields["aadhaar_number"] = f"XXXX XXXX {str(ref)[:4]}"

        if not fields.get("name"):
            logger.info("Decompressed Aadhaar payload did not yield a valid name field.")
            return None

        cleaned = {k: v.strip() if isinstance(v, str) else v for k, v in fields.items() if v is not None}
        return cleaned if cleaned else None

    except Exception as e:
        logger.warning(f"Aadhaar QR parsing failed during byte extraction: {e}")
        return None


def parse_aadhaar_qr(raw_payload: str) -> Optional[Dict[str, Any]]:
    """Master Aadhaar QR parser: supports both XML and Secure QR formats."""
    if not raw_payload:
        return None
    raw_clean = raw_payload.strip()
    if "<PrintLetterBarcodeData" in raw_clean or "<" in raw_clean:
        xml_res = parse_aadhaar_xml_qr(raw_clean)
        if xml_res:
            return xml_res
    return parse_aadhaar_secure_qr(raw_payload)


# ============================================================================
# Driving Licence QR: best-effort parser for multi-state formats
# ============================================================================

_URL_PATTERN = re.compile(r'^https?://', re.IGNORECASE)
_DL_TOKEN_PATTERN = re.compile(r'\b[A-Z]{2}[0-9]{2}[0-9A-Z]{6,13}\b')
_DATE_TOKEN_PATTERN = re.compile(r'\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b')


def parse_dl_qr(raw_payload: str) -> Optional[Dict[str, Any]]:
    """Best-effort DL QR parser supporting JSON, text lines, and token extraction."""
    if not raw_payload:
        return None

    raw = raw_payload.strip()

    # 1. Try JSON payload
    if (raw.startswith("{") and raw.endswith("}")) or (raw.startswith("[") and raw.endswith("]")):
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                dl_val = data.get("dlNo") or data.get("dl_number") or data.get("id_number") or data.get("dl")
                if dl_val:
                    dl_str = str(dl_val).strip()
                    return {
                        "id_number": dl_str,
                        "dl_number": dl_str,
                        "name": str(data.get("name", "")).strip() or None,
                        "dob": str(data.get("dob", "")).strip() or None,
                        "issue_date": str(data.get("issueDate", data.get("issue_date", ""))).strip() or None,
                        "expiry_date": str(data.get("expiryDate", data.get("expiry_date", ""))).strip() or None,
                    }
        except Exception:
            pass

    # 2. Check for URL
    if _URL_PATTERN.match(raw):
        dl_match = _DL_TOKEN_PATTERN.search(raw.upper())
        if dl_match:
            dl_val = dl_match.group(0)
            return {
                "id_number": dl_val,
                "dl_number": dl_val,
                "verification_url": raw,
            }
        return {"verification_url": raw, "_url_only": True}

    # 3. Look for standard DL token pattern
    dl_match = _DL_TOKEN_PATTERN.search(raw.upper())
    if not dl_match:
        return None

    dl_val = dl_match.group(0)
    fields: Dict[str, Any] = {
        "id_number": dl_val,
        "dl_number": dl_val,
    }

    # Extract DOB if present
    dob_match = re.search(r'(?:dob|birth|d\.o\.b)[\s:]*([0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{4})', raw, re.IGNORECASE)
    if dob_match:
        fields["dob"] = dob_match.group(1)
    else:
        date_match = _DATE_TOKEN_PATTERN.search(raw)
        if date_match:
            fields["dob"] = date_match.group(0)

    # Extract Name if labeled
    name_match = re.search(r'(?:name|holder)[\s:]*([A-Za-z\s]{3,40})(?:[\n\r,;|]|$)', raw, re.IGNORECASE)
    if name_match:
        cand = name_match.group(1).strip()
        if len(cand) >= 3 and not any(k in cand.lower() for k in ["licence", "license", "authority"]):
            fields["name"] = cand.upper()

    return fields


def extract_qr_data(img: Image.Image, expected_type: str) -> Optional[Dict[str, Any]]:
    """Detects a QR on the given image and parses it according to the expected document type."""
    raw = detect_and_decode_qr(img)
    if not raw:
        return None

    if expected_type == "aadhaar_card":
        return parse_aadhaar_qr(raw)
    elif expected_type == "driving_licence":
        return parse_dl_qr(raw)
    return None
