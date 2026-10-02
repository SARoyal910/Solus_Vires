// Cleans a photo or screenshot before it is encrypted (P2-E7).
//
// Photos carry hidden details: EXIF can hold the GPS position where a photo
// was taken, the phone model, and more. Redrawing the image on a canvas and
// encoding a fresh JPEG or PNG keeps only the pixels. The result is then
// checked byte by byte; if any metadata block survived, the photo is refused
// rather than saved. What is visible in the picture itself stays.
//
// The capture date ("taken") is read from EXIF before it is dropped, because
// it can matter as evidence. It is stored only inside the encrypted
// description. GPS is never read or kept.
(function () {
  "use strict";

  const MAX_OUTPUT_BYTES = 5 * 1024 * 1024; // the vault's per-photo cap
  const MAX_INPUT_BYTES = 40 * 1024 * 1024; // larger files risk running a phone out of memory
  const MAX_SIDE = 4096; // canvas limits on older iPhones

  class CleanError extends Error {
    constructor(code) {
      super(code);
      this.code = code;
    }
  }

  const ascii = (bytes, start, length) => String.fromCharCode(...bytes.subarray(start, start + length));

  // Lists the metadata blocks in a JPEG or PNG. JPEG: every APPn segment
  // except JFIF (APP0), colour profile (APP2), and Adobe colour (APP14), plus
  // comments. PNG: eXIf, text, and time chunks. Empty means clean.
  function findMetadata(bytes) {
    const found = [];
    if (bytes[0] === 0xff && bytes[1] === 0xd8) {
      let i = 2;
      while (i + 4 <= bytes.length) {
        if (bytes[i] !== 0xff) break;
        const marker = bytes[i + 1];
        if (marker === 0xd8 || marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) {
          i += 2;
          continue;
        }
        if (marker === 0xd9 || marker === 0xda) break; // end of image / start of pixel data
        const length = (bytes[i + 2] << 8) | bytes[i + 3];
        const isApp = marker >= 0xe0 && marker <= 0xef;
        if (marker === 0xfe) found.push("JPEG comment");
        if (isApp && ![0xe0, 0xe2, 0xee].includes(marker)) {
          const label = ascii(bytes, i + 4, 4) === "Exif" ? "EXIF" : ascii(bytes, i + 4, 8) === "http://n" ? "XMP" : `APP${marker - 0xe0}`;
          found.push(label);
        }
        i += 2 + length;
      }
      return found;
    }
    if (bytes[0] === 0x89 && ascii(bytes, 1, 3) === "PNG") {
      let i = 8;
      while (i + 8 <= bytes.length) {
        const length = ((bytes[i] << 24) | (bytes[i + 1] << 16) | (bytes[i + 2] << 8) | bytes[i + 3]) >>> 0;
        const type = ascii(bytes, i + 4, 4);
        if (["eXIf", "tEXt", "iTXt", "zTXt", "tIME"].includes(type)) found.push(`PNG ${type}`);
        if (type === "IEND") break;
        i += 12 + length;
      }
      return found;
    }
    return ["unknown format"];
  }

  // The EXIF DateTimeOriginal (or DateTime) of a JPEG, as "YYYY-MM-DDTHH:MM:SS"
  // in the camera's local time, or null.
  function readExifDate(bytes) {
    if (!(bytes[0] === 0xff && bytes[1] === 0xd8)) return null;
    let i = 2;
    while (i + 4 <= bytes.length && bytes[i] === 0xff) {
      const marker = bytes[i + 1];
      if (marker === 0xda || marker === 0xd9) return null;
      const length = (bytes[i + 2] << 8) | bytes[i + 3];
      if (marker === 0xe1 && ascii(bytes, i + 4, 6) === "Exif\0\0") {
        try {
          return dateFromTiff(bytes.subarray(i + 10, i + 2 + length));
        } catch (e) {
          return null;
        }
      }
      i += 2 + length;
    }
    return null;
  }

  function dateFromTiff(tiff) {
    const little = ascii(tiff, 0, 2) === "II";
    const u16 = (o) => (little ? tiff[o] | (tiff[o + 1] << 8) : (tiff[o] << 8) | tiff[o + 1]);
    const u32 = (o) => (little
      ? (tiff[o] | (tiff[o + 1] << 8) | (tiff[o + 2] << 16) | (tiff[o + 3] << 24)) >>> 0
      : ((tiff[o] << 24) | (tiff[o + 1] << 16) | (tiff[o + 2] << 8) | tiff[o + 3]) >>> 0);
    const entries = (ifd) => {
      const out = new Map();
      const n = u16(ifd);
      for (let k = 0; k < n; k++) {
        const e = ifd + 2 + k * 12;
        out.set(u16(e), { count: u32(e + 4), value: u32(e + 8) });
      }
      return out;
    };
    const asDate = (entry) => {
      if (!entry || entry.count < 19) return null;
      const text = ascii(tiff, entry.value, 19);
      const m = /^(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})$/.exec(text);
      return m ? `${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}` : null;
    };
    const ifd0 = entries(u32(4));
    const exifPointer = ifd0.get(0x8769);
    const exif = exifPointer ? entries(exifPointer.value) : new Map();
    return asDate(exif.get(0x9003)) || asDate(ifd0.get(0x0132));
  }

  async function decode(file) {
    if (typeof createImageBitmap === "function") {
      try {
        const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
        return { source: bitmap, width: bitmap.width, height: bitmap.height, done: () => bitmap.close() };
      } catch (e) {
        // fall back to <img>
      }
    }
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.src = url;
    try {
      await img.decode();
    } catch (e) {
      URL.revokeObjectURL(url);
      throw new CleanError("unreadable");
    }
    return { source: img, width: img.naturalWidth, height: img.naturalHeight, done: () => URL.revokeObjectURL(url) };
  }

  const toBlob = (canvas, type, quality) => new Promise((resolve) => canvas.toBlob(resolve, type, quality));

  // Returns { bytes, type, width, height, taken } or throws CleanError with
  // code "not-image", "too-large", "unreadable", or "metadata-remains".
  async function cleanImage(file) {
    if (!file || !/^image\//.test(file.type || "")) throw new CleanError("not-image");
    if (file.size > MAX_INPUT_BYTES) throw new CleanError("too-large");
    const head = new Uint8Array(await file.slice(0, 256 * 1024).arrayBuffer());
    const taken = readExifDate(head);

    const image = await decode(file);
    try {
      let scale = Math.min(1, MAX_SIDE / Math.max(image.width, image.height));
      let type = file.type === "image/png" ? "image/png" : "image/jpeg";
      let quality = 0.92;
      for (let attempt = 0; attempt < 12; attempt++) {
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(image.width * scale));
        canvas.height = Math.max(1, Math.round(image.height * scale));
        const ctx = canvas.getContext("2d");
        if (type === "image/jpeg") {
          ctx.fillStyle = "#ffffff"; // JPEG has no transparency
          ctx.fillRect(0, 0, canvas.width, canvas.height);
        }
        ctx.drawImage(image.source, 0, 0, canvas.width, canvas.height);
        const blob = await toBlob(canvas, type, quality);
        if (!blob) throw new CleanError("unreadable");
        if (blob.size <= MAX_OUTPUT_BYTES) {
          const bytes = new Uint8Array(await blob.arrayBuffer());
          if (findMetadata(bytes).length) throw new CleanError("metadata-remains");
          return { bytes, type, width: canvas.width, height: canvas.height, taken };
        }
        // Too big: PNG becomes JPEG, then lower quality, then smaller.
        if (type === "image/png") type = "image/jpeg";
        else if (quality > 0.65) quality -= 0.1;
        else scale *= 0.8;
      }
      throw new CleanError("too-large");
    } finally {
      image.done();
    }
  }

  window.ImageClean = { cleanImage, findMetadata, readExifDate, CleanError, MAX_OUTPUT_BYTES };
})();
