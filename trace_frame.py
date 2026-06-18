"""Trace the WHOLE frame front out of farer-outline.png -- outer silhouette plus both
lens openings -- into a single filled SVG (even-odd, so the openings are holes).  Feed it
to extrude_frame.py, which just extrudes it into the glasses front (the bridge / nose gap
come straight from the traced shape, so the nose has real room).

Any frame-front PNG (dark frame on light background) works; swap SRC.
"""
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SRC = "farer-outline.png"
OUT = "examples/wayfarer-frame.svg"

im = np.array(Image.open(SRC).convert("RGB"))
frame = im.mean(2) < 128                                   # dark frame pixels

cs = plt.contour(frame.astype(float), levels=[0.5])
loops = [s for s in cs.allsegs[0] if len(s) > 30]          # drop tiny specks


def bbarea(s):
    return (s[:, 0].max() - s[:, 0].min()) * (s[:, 1].max() - s[:, 1].min())


loops.sort(key=bbarea, reverse=True)
outer = loops[0]
holes = sorted(loops[1:3], key=lambda s: s[:, 0].mean())   # left, right openings
print(f"outer {len(outer)}pts, holes {[len(h) for h in holes]}pts")


def smooth(poly, k=7):
    poly = poly[:-1] if np.allclose(poly[0], poly[-1]) else poly
    pad = k // 2
    xp = np.r_[poly[-pad:, 0], poly[:, 0], poly[:pad, 0]]
    yp = np.r_[poly[-pad:, 1], poly[:, 1], poly[:pad, 1]]
    return np.stack([np.convolve(xp, np.ones(k) / k, "valid"),
                     np.convolve(yp, np.ones(k) / k, "valid")], 1)


def resample(poly, n):
    d = np.r_[0, np.cumsum(np.hypot(*np.diff(np.vstack([poly, poly[:1]]), axis=0).T))]
    u = np.linspace(0, d[-1], n, endpoint=False)
    p = np.vstack([poly, poly[:1]])
    return np.stack([np.interp(u, d, p[:, 0]), np.interp(u, d, p[:, 1])], 1)


outer = resample(smooth(outer), 360)
holes = [resample(smooth(h), 240) for h in holes]

allpts = np.vstack([outer] + holes)
x0, y0 = allpts[:, 0].min(), allpts[:, 1].min()
W = allpts[:, 0].max() - x0
H = allpts[:, 1].max() - y0


def pathstr(s):
    s = s - [x0, y0]
    return "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in s) + " Z"


d = " ".join(pathstr(s) for s in [outer] + holes)
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.1f}" height="{H:.1f}" '
       f'viewBox="0 0 {W:.1f} {H:.1f}">'
       f'<path fill-rule="evenodd" fill="black" d="{d}"/></svg>')
with open(OUT, "w") as f:
    f.write(svg)
print(f"wrote {OUT}  (frame {W:.0f}x{H:.0f}px, outer + {len(holes)} openings)")
