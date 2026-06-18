"""Trace one lens opening out of farer-outline.png (a Wayfarer front silhouette) into a
closed SVG path that the acetate pipeline can use as the lens outline.

No potrace/skimage/cv2 available, so: threshold -> flood-fill the outside background ->
the enclosed white blobs are the two lens openings -> take the right one -> marching-
squares contour (matplotlib) -> write SVG.  Reports the opening / outer widths in px so
the frame can be scaled to the user's 140 mm front.
"""
from collections import deque
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SRC = "farer-outline.png"
OUT = "examples/wayfarer-lens.svg"

im = np.array(Image.open(SRC).convert("RGB"))
H, W = im.shape[:2]
frame = im.mean(2) < 128                       # black frame pixels
white = ~frame

# flood-fill white from the border -> the outside background
outside = np.zeros_like(white)
dq = deque()
for x in range(W):
    for y in (0, H - 1):
        if white[y, x]:
            dq.append((y, x)); outside[y, x] = True
for y in range(H):
    for x in (0, W - 1):
        if white[y, x]:
            dq.append((y, x)); outside[y, x] = True
while dq:
    y, x = dq.popleft()
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ny, nx = y + dy, x + dx
        if 0 <= ny < H and 0 <= nx < W and white[ny, nx] and not outside[ny, nx]:
            outside[ny, nx] = True; dq.append((ny, nx))

openings = white & ~outside                    # enclosed white = the two lens holes
xs = np.where(openings.any(0))[0]
print(f"openings span x[{xs.min()},{xs.max()}], outer frame x span -> measure black:")
fx = np.where(frame.any(0))[0]
outer_w = fx.max() - fx.min()
print(f"outer frame width = {outer_w}px")

# right half opening (image-right); mirror handled later in the pipeline
midx = W // 2
right = openings.copy(); right[:, :midx] = False
ox = np.where(right.any(0))[0]
oy = np.where(right.any(1))[0]
open_w = ox.max() - ox.min()
print(f"right opening width = {open_w}px, height = {oy.max()-oy.min()}px")

# marching-squares contour of the opening at the 0.5 isolevel
cs = plt.contour(right.astype(float), levels=[0.5])
segs = cs.allsegs[0]
poly = max(segs, key=len)[:-1]                 # (N,2) in (x_col, y_row); drop closing dup
# circular smoothing to take the pixel stair-step off the acetate edge AND round the
# tight corners (e.g. lower-nasal) enough that the groove's inward offset can't self-fold
k = 11; pad = k // 2
xp = np.r_[poly[-pad:, 0], poly[:, 0], poly[:pad, 0]]
yp = np.r_[poly[-pad:, 1], poly[:, 1], poly[:pad, 1]]
poly = np.stack([np.convolve(xp, np.ones(k) / k, "valid"),
                 np.convolve(yp, np.ones(k) / k, "valid")], 1)
# resample to ~220 evenly-spaced points
d = np.r_[0, np.cumsum(np.hypot(*np.diff(poly, axis=0).T))]
u = np.linspace(0, d[-1], 220, endpoint=False)
poly = np.stack([np.interp(u, d, poly[:, 0]), np.interp(u, d, poly[:, 1])], 1)

x0, y0 = poly[:, 0].min(), poly[:, 1].min()
pts = poly - [x0, y0]
w, h = pts[:, 0].max(), pts[:, 1].max()
path = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in pts) + " Z"
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.1f}" height="{h:.1f}" '
       f'viewBox="0 0 {w:.1f} {h:.1f}"><path d="{path}" fill="black"/></svg>')
with open(OUT, "w") as f:
    f.write(svg)
print(f"wrote {OUT}  ({len(pts)} pts, {w:.0f}x{h:.0f}px)")
print(f"SCALE HINT: opening is {open_w}px of a {outer_w}px frame; for a 140mm front set "
      f"OUTLINE_WIDTH_MM = {140 * open_w / outer_w:.1f}")
