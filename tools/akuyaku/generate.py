#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@悪役の言葉 カルーセル生成エンジン
------------------------------------
名言テキスト（JSON）を渡すと、既存の絵柄そのままで 3 枚組（1080x1350）を書き出す。

  1枚目: 名言 + 出典  （黒→ワインレッドの縦グラデ・明朝白文字）
  2枚目: 解釈/深掘り   （ほぼ黒の無地・明朝白文字）
  3枚目: 無言のアウトロ（暗いグラデのみ）

使い方:
  python3 tools/akuyaku/generate.py tools/akuyaku/content.example.json
  python3 tools/akuyaku/generate.py <content.json> [出力ルート]

寸法・色・字サイズは posts/2026-07-20 の実測値に合わせてある。
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

# ---- 版面定数（実測ベース） -------------------------------------------------
W, H = 1080, 1350
SS = 2  # スーパーサンプリング倍率（2倍で描いて縮小＝アンチエイリアス）

FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "fonts", "NotoSerifJP.ttf")

# 縦グラデの制御点（縦位置の割合 -> RGB）。posts/2026-07-20/01_1・01_3 の実測。
GRAD_QUOTE = [  # 1枚目・3枚目共通の「黒→ワイン」タイプ（濃いめ）
    (0.00, (44, 15, 18)),
    (0.15, (17, 8, 11)),
    (0.30, (25, 10, 13)),
    (0.45, (33, 10, 16)),
    (0.60, (44, 11, 18)),
    (0.75, (52, 12, 20)),
    (0.90, (61, 16, 23)),
    (1.00, (78, 17, 25)),
]
GRAD_OUTRO = [  # 3枚目（より暗く静か）
    (0.00, (44, 15, 18)),
    (0.15, (10, 10, 12)),
    (0.30, (12, 10, 15)),
    (0.45, (16, 11, 17)),
    (0.60, (17, 12, 18)),
    (0.75, (19, 14, 20)),
    (0.90, (22, 15, 22)),
    (1.00, (55, 15, 24)),
]
SOLID_BODY = (12, 12, 14)  # 2枚目の無地背景

# 文字色
C_QUOTE = (246, 242, 242)
C_SOURCE = (206, 199, 199)
C_BODY = (242, 238, 238)
C_HANDLE = (230, 226, 226)

# 字サイズ（1x基準）と行送り
QUOTE_SIZE, QUOTE_LH, QUOTE_W = 78, 106, 620      # 太さ wght
SOURCE_SIZE, SOURCE_W = 34, 600
BODY_SIZE, BODY_LH, BODY_W = 42, 69, 500
HANDLE_SIZE, HANDLE_W = 30, 500

SIDE_MARGIN = 130           # 本文の左右余白（1x）
QUOTE_MAX_W = W - SIDE_MARGIN * 2
BODY_MAX_W = W - SIDE_MARGIN * 2


# ---- フォント（可変フォントの太さ切替） -------------------------------------
_font_cache = {}


def font(size, weight):
    key = (size, weight)
    if key not in _font_cache:
        f = ImageFont.truetype(FONT_PATH, size * SS)
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
        _font_cache[key] = f
    return _font_cache[key]


# ---- 背景 -------------------------------------------------------------------
def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient(points):
    img = Image.new("RGB", (W * SS, H * SS))
    px = img.load()
    hh = H * SS
    # 縦方向に制御点間を線形補間
    col = []
    for y in range(hh):
        f = y / (hh - 1)
        # 区間を探す
        for i in range(len(points) - 1):
            f0, c0 = points[i]
            f1, c1 = points[i + 1]
            if f0 <= f <= f1:
                t = 0 if f1 == f0 else (f - f0) / (f1 - f0)
                col.append(_lerp(c0, c1, t))
                break
        else:
            col.append(points[-1][1])
    for y in range(hh):
        c = col[y]
        for x in range(W * SS):
            px[x, y] = c
    return img


def gradient_fast(points):
    """1px幅の縦グラデを作って横に引き伸ばす（高速版）。"""
    hh = H * SS
    strip = Image.new("RGB", (1, hh))
    sp = strip.load()
    for y in range(hh):
        f = y / (hh - 1)
        c = points[-1][1]
        for i in range(len(points) - 1):
            f0, c0 = points[i]
            f1, c1 = points[i + 1]
            if f0 <= f <= f1:
                t = 0 if f1 == f0 else (f - f0) / (f1 - f0)
                c = _lerp(c0, c1, t)
                break
        sp[0, y] = c
    return strip.resize((W * SS, hh))


def solid(color):
    return Image.new("RGB", (W * SS, H * SS), color)


# ---- テキスト測定 & 折り返し -----------------------------------------------
def text_w(draw, s, fnt):
    if not s:
        return 0
    return draw.textbbox((0, 0), s, font=fnt)[2]


def wrap_cjk(draw, text, fnt, max_w):
    """幅で折り返し（日本語は任意位置で改行可、\n は明示改行）。"""
    lines = []
    for para in text.split("\n"):
        if para == "":
            lines.append("")
            continue
        cur = ""
        for ch in para:
            if text_w(draw, cur + ch, fnt) <= max_w or cur == "":
                cur += ch
            else:
                lines.append(cur)
                cur = ch
        lines.append(cur)
    return lines


def draw_centered_block(draw, lines, fnt, color, cy, line_h):
    """行群を水平中央・指定した縦中心に配置して描画。戻り値は (top, bottom)。"""
    total = line_h * (len(lines) - 1) if len(lines) > 1 else 0
    # 1行の実高さ
    asc, desc = fnt.getmetrics()
    line_px = asc + desc
    block_h = total + line_px
    top = cy - block_h // 2
    y = top
    for ln in lines:
        w = text_w(draw, ln, fnt)
        draw.text(((W * SS - w) // 2, y), ln, font=fnt, fill=color)
        y += line_h
    return top, top + block_h


# ---- 各スライド -------------------------------------------------------------
def slide_quote(quote, source):
    img = gradient_fast(GRAD_QUOTE)
    d = ImageDraw.Draw(img)
    qf = font(QUOTE_SIZE, QUOTE_W)
    lines = wrap_cjk(d, quote, qf, QUOTE_MAX_W * SS)
    # 名言ブロックの縦中心 = 実測 639 付近
    cy = int(0.472 * H * SS)
    top, bottom = draw_centered_block(d, lines, qf, C_QUOTE, cy, QUOTE_LH * SS)
    # 出典（名言ブロックの下 70px）
    if source:
        sf = font(SOURCE_SIZE, SOURCE_W)
        sw = text_w(d, source, sf)
        d.text(((W * SS - sw) // 2, bottom + 40 * SS), source, font=sf, fill=C_SOURCE)
    _handle(d, pos="right")
    return _finish(img)


def slide_body(text):
    img = solid(SOLID_BODY)
    d = ImageDraw.Draw(img)
    bf = font(BODY_SIZE, BODY_W)
    lines = wrap_cjk(d, text, bf, BODY_MAX_W * SS)
    cy = int(0.47 * H * SS)
    draw_centered_block(d, lines, bf, C_BODY, cy, BODY_LH * SS)
    _handle(d, pos="center")
    return _finish(img)


def slide_outro():
    return _finish(gradient_fast(GRAD_OUTRO))


def _handle(d, pos):
    hf = font(HANDLE_SIZE, HANDLE_W)
    txt = "@悪役の言葉"
    w = text_w(d, txt, hf)
    if pos == "right":
        x = W * SS - w - 50 * SS
        y = H * SS - 73 * SS
    else:  # center
        x = (W * SS - w) // 2
        y = H * SS - 89 * SS
    d.text((x, y), txt, font=hf, fill=C_HANDLE)


def _finish(img):
    return img.resize((W, H), Image.LANCZOS)


# ---- エントリポイント -------------------------------------------------------
def generate(content_path, out_root=None):
    with open(content_path, encoding="utf-8") as f:
        data = json.load(f)
    date = data["date"]
    out_root = out_root or os.path.join(
        os.path.dirname(__file__), "..", "..", "posts", date
    )
    os.makedirs(out_root, exist_ok=True)
    made = []
    for i, post in enumerate(data["posts"], start=1):
        nn = f"{i:02d}"
        s1 = slide_quote(post["quote"], post.get("source", ""))
        s2 = slide_body(post["interpretation"])
        s3 = slide_outro()
        for suffix, im in ((1, s1), (2, s2), (3, s3)):
            path = os.path.join(out_root, f"{nn}_{suffix}.jpg")
            im.save(path, "JPEG", quality=92)
            made.append(path)
    print(f"生成完了: {len(made)} 枚 -> {os.path.normpath(out_root)}")
    for p in made:
        print("  ", os.path.normpath(p))
    return made


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: generate.py <content.json> [out_root]", file=sys.stderr)
        sys.exit(1)
    generate(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
