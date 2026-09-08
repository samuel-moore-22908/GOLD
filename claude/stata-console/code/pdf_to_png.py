"""
Rasterise a Stata-exported PDF to PNG, because Stata's own PNG export crashes.

THE PROBLEM. `graph export foo.png, width(2800)` on a large graph takes down
Stata 18/MP on Windows - not an error, a process death, so nothing is written to
the log and the session is gone. Observed on the figure-1 panel, which is 13 x
7.4 inches; the PDF export of the same graph immediately before it succeeds
every time. The failure is in the Windows rasteriser, not in the drawing, the
font or the glyph set (all of which were checked and cleared first).

WHY THIS IS ALSO JUST BETTER. Stata's PNG is rasterised from its own display
list at whatever dpi width()/xsize() implies. Going through the PDF means the
raster is produced from vectors by MuPDF, so text and hairlines come out
cleaner at the same pixel count, and the pixel count can be changed later
without re-running Stata.

Usage:
    python pdf_to_png.py FIGURE.pdf                # 2800px wide, alongside it
    python pdf_to_png.py FIGURE.pdf --width 1400
    python pdf_to_png.py FIGURE.pdf -o OTHER.png
    python pdf_to_png.py DIR --width 2400          # every .pdf in DIR
"""
import argparse
import sys
from pathlib import Path

import pymupdf

DEFAULT_WIDTH = 2800


def convert(pdf, width=DEFAULT_WIDTH, out=None):
    """Render page 1 of `pdf` to a PNG `width` pixels across. Returns the path."""
    pdf = Path(pdf)
    out = Path(out) if out else pdf.with_suffix(".png")
    with pymupdf.open(pdf) as doc:
        if doc.page_count == 0:
            raise SystemExit(f"{pdf.name}: no pages")
        page = doc[0]
        # Page geometry is in points at 72/inch. Scaling by the ratio of the
        # wanted pixel width to the page width in points reproduces Stata's
        # width() semantics exactly, so figures keep the dimensions they had.
        zoom = width / page.rect.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        pix.save(out)
    return out, pix.width, pix.height


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("target", help="a .pdf, or a directory of them")
    ap.add_argument("--width", type=int, default=DEFAULT_WIDTH,
                    help=f"output width in pixels (default {DEFAULT_WIDTH})")
    ap.add_argument("-o", "--out", help="output path; single-file input only")
    a = ap.parse_args()

    target = Path(a.target)
    if target.is_dir():
        pdfs = sorted(target.glob("*.pdf"))
        if a.out:
            raise SystemExit("-o cannot be combined with a directory")
    elif target.is_file():
        pdfs = [target]
    else:
        raise SystemExit(f"no such file or directory: {target}")
    if not pdfs:
        raise SystemExit(f"no PDFs in {target}")

    for p in pdfs:
        out, w, h = convert(p, a.width, a.out)
        print(f"  {p.name} -> {out.name}  {w}x{h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
