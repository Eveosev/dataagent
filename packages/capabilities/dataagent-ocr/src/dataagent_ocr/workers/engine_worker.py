"""Standalone OCR worker for dependency-based engines.

Copied into ``<data_root>/ocr/engines/<engine>/worker.py`` at install time and
run with that engine's own interpreter (``python -I worker.py --engine X``).
Standard library plus the engine's packages only; never imports dataagent.
Protocol: see ``dataagent_ocr.providers.worker``.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import sys
import traceback


def _boxes_from_poly(poly):
    xs = [float(p[0]) for p in poly]
    ys = [float(p[1]) for p in poly]
    return [min(xs), min(ys), max(xs), max(ys)]


def _to_list(value):
    return value.tolist() if hasattr(value, "tolist") else value


def _version(module, *dists):
    """Module ``__version__``, else the installed distribution version."""

    value = getattr(module, "__version__", None)
    if value:
        return str(value)
    from importlib import metadata

    for name in dists:
        try:
            return metadata.version(name)
        except metadata.PackageNotFoundError:
            continue
    return "unknown"


def paddle_blocks(result):
    """Normalize PaddleOCR 3.x ``predict`` results and 2.x ``ocr`` results."""

    blocks = []
    items = list(result or [])
    for item in items:
        res = None
        if isinstance(item, dict):
            res = item.get("res", item)
        elif hasattr(item, "json"):
            data = item.json
            res = data.get("res", data) if isinstance(data, dict) else None
        if isinstance(res, dict) and "rec_texts" in res:
            texts = _to_list(res.get("rec_texts")) or []
            scores = _to_list(res.get("rec_scores")) or [None] * len(texts)
            boxes = _to_list(res.get("rec_boxes"))
            polys = _to_list(res.get("rec_polys"))
            for index, text in enumerate(texts):
                if boxes is not None and len(boxes) > index and len(boxes[index]) == 4:
                    bbox = [float(v) for v in boxes[index]]
                elif polys is not None and len(polys) > index:
                    bbox = _boxes_from_poly(polys[index])
                else:
                    bbox = []
                score = scores[index] if index < len(scores) else None
                blocks.append({"text": str(text), "bbox": bbox, "confidence": None if score is None else float(score)})
            continue
        # PaddleOCR 2.x: [[ [poly, (text, score)], ... ]] (one list per image)
        lines = item if isinstance(item, list) else []
        for line in lines or []:
            try:
                poly, (text, score) = line[0], line[1]
            except (TypeError, ValueError, IndexError):
                continue
            blocks.append({"text": str(text), "bbox": _boxes_from_poly(poly), "confidence": float(score)})
    return blocks


class PaddleEngine:
    name = "paddleocr"

    def __init__(self, lang):
        import paddleocr  # noqa: F401 - engine_missing on ImportError

        self.version = _version(paddleocr, "paddleocr")
        self._lang = lang
        self._cache = {}

    def _ocr(self, lang):
        key = lang or self._lang or "ch"
        if key not in self._cache:
            from paddleocr import PaddleOCR

            try:
                self._cache[key] = PaddleOCR(
                    lang=key,
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                )
            except TypeError:  # 2.x signature
                self._cache[key] = PaddleOCR(lang=key, use_angle_cls=True, show_log=False)
        return self._cache[key]

    def recognize(self, image, lang):
        import numpy as np

        array = np.array(image.convert("RGB"))[:, :, ::-1]  # PaddleOCR expects BGR
        ocr = self._ocr(lang)
        if hasattr(ocr, "predict"):
            return paddle_blocks(ocr.predict(array))
        return paddle_blocks(ocr.ocr(array, cls=True))


class RapidEngine:
    name = "rapidocr"

    def __init__(self, lang):
        try:
            import rapidocr_onnxruntime as module
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            import rapidocr as module
            from rapidocr import RapidOCR
        self.version = _version(module, "rapidocr-onnxruntime", "rapidocr")
        self._engine = RapidOCR()

    def recognize(self, image, lang):
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="PNG")
        output = self._engine(buffer.getvalue())
        result = output[0] if isinstance(output, tuple) else getattr(output, "txts", None)
        blocks = []
        if isinstance(output, tuple):
            for box, text, score in result or []:
                blocks.append({"text": str(text), "bbox": _boxes_from_poly(box), "confidence": float(score)})
        else:  # rapidocr >= 2 returns an object with boxes/txts/scores
            for box, text, score in zip(_to_list(output.boxes) or [], output.txts or [], output.scores or []):
                blocks.append({"text": str(text), "bbox": _boxes_from_poly(box), "confidence": float(score)})
        return blocks


class EasyEngine:
    name = "easyocr"

    def __init__(self, lang):
        import easyocr

        self.version = _version(easyocr, "easyocr")
        langs = [part for part in (lang or "en").split("+") if part]
        self._reader = easyocr.Reader(langs, gpu=False)

    def recognize(self, image, lang):
        import numpy as np

        blocks = []
        for poly, text, score in self._reader.readtext(np.array(image.convert("RGB"))):
            blocks.append({"text": str(text), "bbox": _boxes_from_poly(poly), "confidence": float(score)})
        return blocks


class TesseractEngine:
    name = "tesseract"

    def __init__(self, lang):
        import pytesseract

        self._pt = pytesseract
        self.version = str(pytesseract.get_tesseract_version())
        self._lang = lang or "eng"

    def recognize(self, image, lang):
        data = self._pt.image_to_data(image, lang=lang or self._lang, output_type=self._pt.Output.DICT)
        lines = {}
        for i, text in enumerate(data["text"]):
            if not str(text).strip():
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            conf = float(data["conf"][i])
            entry = lines.setdefault(key, {"words": [], "box": [x, y, x + w, y + h], "confs": []})
            entry["words"].append(str(text))
            box = entry["box"]
            entry["box"] = [min(box[0], x), min(box[1], y), max(box[2], x + w), max(box[3], y + h)]
            if conf >= 0:
                entry["confs"].append(conf / 100.0)
        blocks = []
        for key in sorted(lines):
            entry = lines[key]
            confs = entry["confs"]
            blocks.append(
                {
                    "text": " ".join(entry["words"]),
                    "bbox": [float(v) for v in entry["box"]],
                    "confidence": (sum(confs) / len(confs)) if confs else None,
                }
            )
        return blocks


ENGINES = {cls.name: cls for cls in (PaddleEngine, RapidEngine, EasyEngine, TesseractEngine)}


def _reply(payload):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def serve(engine_name, lang):
    engine = None
    for line in sys.stdin:
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        rid = request.get("id")
        try:
            if engine is None:
                try:
                    engine = ENGINES[engine_name](lang)
                except ImportError as exc:
                    _reply({"id": rid, "error": {"code": "engine_missing", "message": f"{engine_name}: {exc}"}})
                    continue
            if request.get("op") == "hello":
                _reply({"id": rid, "engine": engine_name, "engine_version": engine.version})
            elif request.get("op") == "recognize":
                from PIL import Image

                image = Image.open(io.BytesIO(base64.b64decode(request["image_b64"])))
                image.load()
                _reply({"id": rid, "blocks": engine.recognize(image, request.get("lang"))})
            else:
                _reply({"id": rid, "error": {"code": "bad_request", "message": "unknown op"}})
        except Exception as exc:  # noqa: BLE001 - reported to the client
            traceback.print_exc(file=sys.stderr)
            _reply({"id": rid, "error": {"code": "engine_error", "message": f"{type(exc).__name__}: {exc}"}})


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True, choices=sorted(ENGINES))
    parser.add_argument("--lang")
    parser.add_argument("--selftest", action="store_true", help="import the engine and print its version")
    args = parser.parse_args(argv)
    if args.selftest:
        engine = ENGINES[args.engine](args.lang)
        print(json.dumps({"engine": args.engine, "engine_version": engine.version}))
        return 0
    serve(args.engine, args.lang)
    return 0


if __name__ == "__main__":
    sys.exit(main())
