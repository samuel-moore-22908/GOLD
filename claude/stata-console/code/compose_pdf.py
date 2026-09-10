"""
Lay PDF figures side by side without asking Stata to combine them.

WHY. graph combine is where the figure-1 panel kills Stata on some machines -
both plain combine and grc1leg2, so it is the operation, not the implementation.
Stata has to hold the left panel, the right panel AND a combined copy of both at
once, and on a large figure that is where it goes down.

Combining two finished PDFs is a page-composition problem, not a graphics one.
MuPDF places existing pages onto a new one without re-rendering anything, so the
vectors, fonts and colours are exactly what Stata wrote.

Panels are placed at their natural size, aligned on their top edge, and the new
page is sized to fit. Give --gap to put space between them.

Usage:
    python compose_pdf.py OUT.pdf LEFT.pdf RIGHT.pdf
    python compose_pdf.py OUT.pdf TOP.pdf BOTTOM.pdf --stack
    python compose_pdf.py OUT.pdf A.pdf B.pdf --gap 12 --png-width 2800
"""
import argparse
import sys
from pathlib import Path

import pymupdf


def compose(out, parts, stack=False, gap=0.0):
    """Place each PDF's first page on one new page. Returns (path, w, h)."""
    srcs = [pymupdf.open(p) for p in parts]
    try:
        boxes = [d[0].rect for d in srcs]
        if stack:
            width = max(b.width for b in boxes)
            height = sum(b.height for b in boxes) + gap * (len(boxes) - 1)
        else:
            width = sum(b.width for b in boxes) + gap * (len(boxes) - 1)
            height = max(b.height for b in boxes)

        doc = pymupdf.open()
        page = doc.new_page(width=width, height=height)
        x = y = 0.0
        for src, box in zip(srcs, boxes):
            # show_pdf_page copies the source page's content stream, so nothing
            # is rasterised and nothing is re-typeset.
            page.show_pdf_page(
                pymupdf.Rect(x, y, x + box.width, y + box.height), src, 0)
            if stack:
                y += box.height + gap
            else:
                x += box.width + gap
        doc.save(out)
        doc.close()
    finally:
        for d in srcs:
            d.close()
    return Path(out), width, height


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("out", help="output PDF")
    ap.add_argument("parts", nargs="+", help="input PDFs, in placement order")
    ap.add_argument("--stack", action="store_true",
                    help="stack vertically instead of side by side")
    ap.add_argument("--gap", type=float, default=0.0,
                    help="points of space between panels (72 = 1 inch)")
    ap.add_argument("--png-width", type=int, default=0,
                    help="also write a PNG this many pixels wide")
    a = ap.parse_args()

    missing = [p for p in a.parts if not Path(p).is_file()]
    if missing:
        raise SystemExit("missing input: " + ", ".join(missing))

    out, w, h = compose(a.out, a.parts, a.stack, a.gap)
    print(f"  wrote {out.name}  {w:.0f}x{h:.0f}pt "
          f"({w/72:.2f}x{h/72:.2f}in) from {len(a.parts)} panels")

    if a.png_width:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from pdf_to_png import convert
        png, pw, ph = convert(out, a.png_width)
        print(f"  wrote {png.name}  {pw}x{ph}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
