#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
أداة خالد لترجمة لغة الإشارة
Khaled's Sign Language Translation Tool

تترجم نصاً عربياً إلى لغة الإشارة العربية (ArSL) عن طريق تهجئة الحروف بالأصابع،
وتُخرج صورة واحدة تجمع إشارات الحروف بالترتيب الصحيح (من اليمين إلى اليسار).

الاستخدام:
    python3 tools/sign_translate.py "النص العربي"
    python3 tools/sign_translate.py            # وضع تفاعلي
    python3 tools/sign_translate.py "مرحبا" -o .tmp/result.png

تتطلب: Pillow  (pip install -r requirements.txt)
"""

import argparse
import json
import os
import sys
import unicodedata

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("خطأ: مكتبة Pillow غير مثبّتة. شغّل:  pip install -r requirements.txt")

# ---------------------------------------------------------------------------
# المسارات
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIGNS_DIR = os.path.join(ROOT, "assets", "signs")
MAPPING_FILE = os.path.join(SIGNS_DIR, "mapping.json")
DEFAULT_OUTPUT = os.path.join(ROOT, ".tmp", "translation.png")

# إعدادات العرض
TILE = 200          # حجم خانة الحرف الواحد (بكسل)
PADDING = 16        # المسافة بين الخانات
LABEL_H = 48        # ارتفاع شريط تسمية الحرف
BG = (255, 255, 255)
LABEL_BG = (33, 90, 160)
LABEL_FG = (255, 255, 255)
MISSING_BG = (245, 230, 230)
MISSING_FG = (170, 60, 60)

# علامات التشكيل العربية التي تُحذف قبل الترجمة
TASHKEEL = "".join(chr(c) for c in range(0x064B, 0x0653)) + "ٰـ"


# ---------------------------------------------------------------------------
# تحميل الخريطة
# ---------------------------------------------------------------------------
def load_mapping():
    if not os.path.exists(MAPPING_FILE):
        sys.exit(f"خطأ: ملف الخريطة غير موجود: {MAPPING_FILE}")
    with open(MAPPING_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return (
        data.get("letters", {}),
        data.get("normalize", {}),
        data.get("_extensions", ["png", "jpg", "jpeg", "webp", "gif"]),
    )


def find_image(basename, extensions):
    """يبحث عن ملف صورة الحرف بأي امتداد مدعوم. يُرجع المسار أو None."""
    # الاسم كما هو في الخريطة (قد يحتوي امتداداً مسبقاً)
    candidates = [basename]
    stem, ext = os.path.splitext(basename)
    if ext:
        candidates.append(stem)
        candidates = [basename]
    else:
        candidates = [f"{basename}.{e}" for e in extensions]
    for name in candidates:
        path = os.path.join(SIGNS_DIR, name)
        if os.path.exists(path):
            return path
    return None


# ---------------------------------------------------------------------------
# معالجة النص
# ---------------------------------------------------------------------------
def normalize_text(text, normalize_map):
    """يحذف التشكيل ويوحّد الهمزات وفق الخريطة."""
    text = unicodedata.normalize("NFC", text)
    out = []
    for ch in text:
        if ch in TASHKEEL:
            continue
        out.append(normalize_map.get(ch, ch))
    return "".join(out)


def tokenize(text, letters):
    """يحوّل النص إلى قائمة عناصر: ('letter', حرف) أو ('space',) أو ('unknown', رمز)."""
    tokens = []
    i = 0
    n = len(text)
    # الإشارات المركّبة (مثل "ال" و"لا") مرتّبة من الأطول للأقصر
    digraphs = sorted((k for k in letters if len(k) > 1), key=len, reverse=True)
    # "ال" التعريف تُدمج فقط في بداية الكلمة
    word_start_only = {"ال"}
    while i < n:
        ch = text[i]
        # دمج الإشارات المركّبة إن وُجدت في الخريطة
        matched = False
        at_word_start = i == 0 or text[i - 1].isspace()
        for dg in digraphs:
            if dg in word_start_only and not at_word_start:
                continue
            if text.startswith(dg, i):
                tokens.append(("letter", dg))
                i += len(dg)
                matched = True
                break
        if matched:
            continue
        if ch.isspace():
            tokens.append(("space",))
        elif ch in letters:
            tokens.append(("letter", ch))
        else:
            tokens.append(("unknown", ch))
        i += 1
    return tokens


# ---------------------------------------------------------------------------
# الخطوط
# ---------------------------------------------------------------------------
def load_font(size):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/GeezaPro.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# بناء الصورة
# ---------------------------------------------------------------------------
def make_tile(token, letters, extensions, font):
    """يبني خانة واحدة (صورة الحرف + تسمية)."""
    kind = token[0]
    if kind == "space":
        return None

    tile = Image.new("RGB", (TILE, TILE + LABEL_H), BG)
    draw = ImageDraw.Draw(tile)

    if kind == "letter":
        letter = token[1]
        img_path = find_image(letters[letter], extensions)
        if img_path:
            try:
                sign = Image.open(img_path).convert("RGB")
                sign.thumbnail((TILE, TILE))
                ox = (TILE - sign.width) // 2
                oy = (TILE - sign.height) // 2
                tile.paste(sign, (ox, oy))
            except Exception:
                img_path = None
        if not img_path:
            # صورة مفقودة
            tile.paste(Image.new("RGB", (TILE, TILE), MISSING_BG), (0, 0))
            draw.text((TILE / 2, TILE / 2), "؟", fill=MISSING_FG,
                      font=load_font(90), anchor="mm")
        label, lbg = letter, LABEL_BG
    else:  # unknown
        symbol = token[1]
        tile.paste(Image.new("RGB", (TILE, TILE), MISSING_BG), (0, 0))
        draw.text((TILE / 2, TILE / 2), symbol if symbol.strip() else "·",
                  fill=MISSING_FG, font=load_font(90), anchor="mm")
        label, lbg = "غير معروف", MISSING_FG

    # شريط التسمية
    draw.rectangle([0, TILE, TILE, TILE + LABEL_H], fill=lbg)
    draw.text((TILE / 2, TILE + LABEL_H / 2), label,
              fill=LABEL_FG, font=font, anchor="mm")
    return tile


def build_image(tokens, letters, extensions):
    """يجمع كل الخانات في صورة واحدة بترتيب من اليمين إلى اليسار."""
    visible = [t for t in tokens if t[0] != "space"]
    if not visible:
        return None, 0, 0

    font = load_font(28)
    tiles = [make_tile(t, letters, extensions, font) for t in tokens]

    # حساب العرض: المسافات تُعرض كفراغ بنصف خانة
    def width_of(tok):
        return TILE // 2 if tok[0] == "space" else TILE

    total_w = sum(width_of(t) for t in tokens) + PADDING * (len(tokens) + 1)
    total_h = TILE + LABEL_H + PADDING * 2
    canvas = Image.new("RGB", (total_w, total_h), BG)

    # الترتيب من اليمين إلى اليسار: أول حرف على أقصى اليمين
    x = total_w - PADDING
    for tok, tile in zip(tokens, tiles):
        w = width_of(tok)
        x -= w
        if tok[0] != "space":
            canvas.paste(tile, (x, PADDING))
        x -= PADDING

    return canvas, len(visible), total_w


# ---------------------------------------------------------------------------
# الرئيسي
# ---------------------------------------------------------------------------
def translate(text, output):
    letters, normalize_map, extensions = load_mapping()
    norm = normalize_text(text, normalize_map)
    tokens = tokenize(norm, letters)

    canvas, count, _ = build_image(tokens, letters, extensions)
    if canvas is None:
        sys.exit("لا يوجد نص قابل للترجمة.")

    os.makedirs(os.path.dirname(output), exist_ok=True)
    canvas.save(output)

    unknown = sorted({t[1] for t in tokens if t[0] == "unknown" and t[1].strip()})
    missing = sorted({t[1] for t in tokens if t[0] == "letter"
                      and not find_image(letters[t[1]], extensions)})

    print("=" * 50)
    print("  أداة خالد لترجمة لغة الإشارة")
    print("=" * 50)
    print(f"النص المُدخل : {text}")
    print(f"عدد الحروف   : {count}")
    print(f"الصورة       : {output}")
    if missing:
        print(f"⚠ حروف بلا صور (ضع ملفاتها في assets/signs/): {' '.join(missing)}")
    if unknown:
        print(f"⚠ رموز غير معروفة (تُجوهلت): {' '.join(unknown)}")
    print("=" * 50)
    return output


def main():
    parser = argparse.ArgumentParser(
        description="أداة خالد لترجمة لغة الإشارة — نص عربي إلى لغة الإشارة العربية")
    parser.add_argument("text", nargs="?", help="النص العربي المراد ترجمته")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="مسار الصورة الناتجة (الافتراضي: .tmp/translation.png)")
    parser.add_argument("--open", action="store_true",
                        help="فتح الصورة الناتجة بعد الإنشاء")
    args = parser.parse_args()

    text = args.text
    if not text:
        try:
            text = input("أدخل النص العربي: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
    if not text:
        sys.exit("لم يُدخَل أي نص.")

    output = translate(text, args.output)

    if args.open:
        if sys.platform == "darwin":
            os.system(f'open "{output}"')
        elif sys.platform.startswith("win"):
            os.startfile(output)  # type: ignore
        else:
            os.system(f'xdg-open "{output}"')


if __name__ == "__main__":
    main()
