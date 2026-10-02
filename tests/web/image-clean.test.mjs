// The metadata scanner and date reader behind photo cleaning (P2-E7). The
// canvas re-encode itself needs a browser: tests/browser/notes_vault.mjs runs
// a GPS-tagged JPEG through it and checks what gets encrypted.
//   node --test tests/web/
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";
import { makeExifApp1, withExif } from "./exif-fixture.mjs";

globalThis.window = globalThis;
vm.runInThisContext(readFileSync(new URL("../../html/image-clean.js", import.meta.url), "utf8"));
const { findMetadata, readExifDate } = globalThis.ImageClean;

// A minimal JPEG skeleton: SOI, JFIF APP0, SOS, a few data bytes, EOI.
const JFIF = [0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00];
const cleanJpeg = new Uint8Array([0xff, 0xd8, ...JFIF, 0xff, 0xda, 0x00, 0x02, 0x11, 0x22, 0xff, 0xd9]);

test("a clean canvas-style JPEG has no metadata", () => {
  assert.deepEqual(findMetadata(cleanJpeg), []);
});

test("a GPS-tagged JPEG is flagged as carrying EXIF", () => {
  assert.deepEqual(findMetadata(withExif(cleanJpeg)), ["EXIF"]);
});

test("XMP, comments, and other APP blocks are flagged; colour profiles are not", () => {
  const xmpText = "http://ns.adobe.com/xap/1.0/\0<x/>";
  const xmp = [0xff, 0xe1, 0, 2 + xmpText.length, ...[...xmpText].map((c) => c.charCodeAt(0))];
  const comment = [0xff, 0xfe, 0, 5, 0x68, 0x69, 0x21];
  const icc = [0xff, 0xe2, 0, 4, 0, 0];
  const jpeg = new Uint8Array([0xff, 0xd8, ...JFIF, ...icc, ...xmp, ...comment, 0xff, 0xda, 0, 2, 0xff, 0xd9]);
  assert.deepEqual(findMetadata(jpeg), ["XMP", "JPEG comment"]);
});

test("PNG text and eXIf chunks are flagged", () => {
  const chunk = (type, len = 0) => [0, 0, 0, len, ...[...type].map((c) => c.charCodeAt(0)), ...new Array(len).fill(0), 0, 0, 0, 0];
  const sig = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
  assert.deepEqual(findMetadata(new Uint8Array([...sig, ...chunk("IHDR", 13), ...chunk("IDAT", 2), ...chunk("IEND")])), []);
  assert.deepEqual(
    findMetadata(new Uint8Array([...sig, ...chunk("IHDR", 13), ...chunk("tEXt", 3), ...chunk("eXIf", 4), ...chunk("IEND")])),
    ["PNG tEXt", "PNG eXIf"],
  );
});

test("the capture date is read from EXIF (it stays, encrypted); nothing else is", () => {
  assert.equal(readExifDate(withExif(cleanJpeg, makeExifApp1({ date: "2025:12:24 07:05:09" }))), "2025-12-24T07:05:09");
  assert.equal(readExifDate(cleanJpeg), null);
});

test("garbage never throws", () => {
  assert.equal(readExifDate(new Uint8Array([0xff, 0xd8, 0xff, 0xe1, 0, 8, 0x45, 0x78, 0x69, 0x66, 0, 0])), null);
  assert.deepEqual(findMetadata(new Uint8Array([1, 2, 3])), ["unknown format"]);
});
