// Builds a real EXIF block (APP1) with a capture date and a GPS position, and
// splices it into a JPEG, so tests can prove the GPS never survives cleaning.
// Used by tests/web/image-clean.test.mjs and tests/browser/notes_vault.mjs.

export const GPS_LAT = [40, 44, 54.36]; // degrees, minutes, seconds
export const GPS_LON = [73, 59, 8.5];

export function makeExifApp1({ date = "2026:09:01 21:14:05" } = {}) {
  // Big-endian TIFF: IFD0 (Exif + GPS pointers) -> Exif IFD (DateTimeOriginal), GPS IFD.
  const buf = new ArrayBuffer(512);
  const v = new DataView(buf);
  const bytes = new Uint8Array(buf);
  let p = 0;
  const str = (s) => { for (const ch of s) bytes[p++] = ch.charCodeAt(0); };
  str("MM"); v.setUint16(p, 42); p += 2; v.setUint32(p, 8); p += 4;

  const entry = (at, tag, type, count, value) => {
    v.setUint16(at, tag); v.setUint16(at + 2, type); v.setUint32(at + 4, count); v.setUint32(at + 8, value);
  };
  const ifd0 = 8, exifIfd = 8 + 2 + 2 * 12 + 4, gpsIfd = exifIfd + 2 + 12 + 4;
  const data = gpsIfd + 2 + 4 * 12 + 4;
  const dateAt = data, latAt = data + 20, lonAt = latAt + 24;

  v.setUint16(ifd0, 2);
  entry(ifd0 + 2, 0x8769, 4, 1, exifIfd);
  entry(ifd0 + 14, 0x8825, 4, 1, gpsIfd);
  v.setUint32(ifd0 + 26, 0);

  v.setUint16(exifIfd, 1);
  entry(exifIfd + 2, 0x9003, 2, 20, dateAt);
  v.setUint32(exifIfd + 14, 0);

  v.setUint16(gpsIfd, 4);
  entry(gpsIfd + 2, 0x0001, 2, 2, 0x4e000000); // "N"
  entry(gpsIfd + 14, 0x0002, 5, 3, latAt);
  entry(gpsIfd + 26, 0x0003, 2, 2, 0x57000000); // "W"
  entry(gpsIfd + 38, 0x0004, 5, 3, lonAt);
  v.setUint32(gpsIfd + 50, 0);

  p = dateAt; str(date); bytes[p++] = 0;
  const rationals = (at, [d, m, s]) => {
    [[d, 1], [m, 1], [Math.round(s * 100), 100]].forEach(([n, den], k) => { v.setUint32(at + k * 8, n); v.setUint32(at + k * 8 + 4, den); });
  };
  rationals(latAt, GPS_LAT);
  rationals(lonAt, GPS_LON);

  const tiff = bytes.subarray(0, lonAt + 24);
  const app1 = new Uint8Array(4 + 6 + tiff.length);
  app1.set([0xff, 0xe1, ((app1.length - 2) >> 8) & 0xff, (app1.length - 2) & 0xff]);
  app1.set([0x45, 0x78, 0x69, 0x66, 0, 0], 4); // "Exif\0\0"
  app1.set(tiff, 10);
  return app1;
}

// Inserts the APP1 right after SOI (where cameras put it).
export function withExif(jpeg, app1 = makeExifApp1()) {
  const out = new Uint8Array(jpeg.length + app1.length);
  out.set(jpeg.subarray(0, 2));
  out.set(app1, 2);
  out.set(jpeg.subarray(2), 2 + app1.length);
  return out;
}

// True if the bytes contain a GPS IFD tag sequence from makeExifApp1.
export function containsGps(bytes) {
  const needle = [0x88, 0x25];
  for (let i = 0; i + 1 < bytes.length; i++) if (bytes[i] === needle[0] && bytes[i + 1] === needle[1]) return true;
  return false;
}
