// utils/uploader.js
/**
 * Custom uploader using native XMLHttpRequest.
 * 
 * In Expo SDK 52+, `global.fetch` is replaced with `expo/fetch` (WinterCG-compliant),
 * which currently lacks FormData support and throws:
 * "[Error: Unsupported FormDataPart implementation]" (tracked in expo/expo #33134).
 * 
 * Native XMLHttpRequest completely bypasses `expo/fetch` and directly uses
 * React Native's native networking stack (RCTNetworking on iOS / OkHttp on Android)
 * which natively supports multipart file uploads.
 */

export class CustomFormData extends FormData {
  getParts() {
    if (!this._parts || !Array.isArray(this._parts)) {
      return typeof super.getParts === 'function' ? super.getParts() : [];
    }
    return this._parts.map(([name, value]) => {
      const headers = { 'content-disposition': `form-data; name="${name}"` };
      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        if (typeof value.name === 'string') {
          headers['content-disposition'] += `; filename="${value.name}"`;
        }
        if (typeof value.type === 'string') {
          headers['content-type'] = value.type;
        }
        return { ...value, headers, fieldName: name };
      }
      return { string: String(value), headers, fieldName: name };
    });
  }
}

export function uploadMultipart(url, formData) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url);
    xhr.timeout = 120000; // 120 seconds timeout for resilient mobile uploads

    xhr.onload = () => {
      try {
        const json = JSON.parse(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve({ ok: true, status: xhr.status, data: json });
        } else {
          resolve({ ok: false, status: xhr.status, data: json });
        }
      } catch (e) {
        resolve({
          ok: false,
          status: xhr.status,
          data: {
            detail: xhr.responseText || `Server returned HTTP ${xhr.status}`,
          },
        });
      }
    };

    xhr.onerror = () => {
      reject(
        new Error(
          'Network request failed. Please ensure the backend is running and reachable on your Wi-Fi network.'
        )
      );
    };

    xhr.ontimeout = () => {
      reject(
        new Error(
          'Request timed out. Document extraction took longer than expected.'
        )
      );
    };

    // NOTE: Do NOT set Content-Type header manually.
    // React Native's native layer sets multipart/form-data with the correct boundary.
    xhr.send(formData);
  });
}
