"""Render the assembled acetate glasses (front + both temples, temples opened) from the
exported STLs, for a quick look.  Writes glasses.png."""
import struct
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def load(p):
    with open(p, "rb") as f:
        f.read(80); n = struct.unpack("<I", f.read(4))[0]; T = []
        for _ in range(n):
            f.read(12); v = [struct.unpack("<3f", f.read(12)) for _ in range(3)]; f.read(2)
            T.append(v)
    return np.array(T)


def place(tris, R, t):
    """rotate (3x3) then translate, vertex by vertex (robust shapes)."""
    flat = tris.reshape(-1, 3) @ R.T + t
    return flat.reshape(tris.shape)


front = load("acetate_front.stl")
temR = load("temple_right.stl")
temL = load("temple_left.stl")

fb = front.reshape(-1, 3)
xmax = fb[:, 0].max()
zmin = fb[:, 2].min()
# the temple's front face is its local z=0; mount it at the endpiece (temporal back),
# pointing back (-Z) with a small outward splay so the arms open like worn glasses.
splay = np.radians(7)
Ry = np.array([[np.cos(splay), 0, np.sin(splay)], [0, 1, 0],
               [-np.sin(splay), 0, np.cos(splay)]])
padR = np.array([xmax - 3.0, 0.0, zmin + 2.0])
temR_p = place(temR, Ry, padR)
padL = np.array([-(xmax - 3.0), 0.0, zmin + 2.0])
temL_p = place(temL, Ry.T, padL)   # opposite splay

allt = [front, temR_p, temL_p]
pts = np.vstack([a.reshape(-1, 3) for a in allt])

fig = plt.figure(figsize=(14, 7))
for i, (az, el, title) in enumerate([(-78, 16, "assembled (front + temples, opened)"),
                                     (-120, 28, "3/4 rear")]):
    ax = fig.add_subplot(1, 2, i + 1, projection="3d")
    for a in allt:
        ax.add_collection3d(Poly3DCollection(a, facecolor=(0.13, 0.13, 0.15),
                            edgecolor=(0, 0, 0, 0.1), linewidth=0.05))
    mn, mx = pts.min(0), pts.max(0); c = (mn + mx) / 2; r = (mx - mn).max() / 2
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1)); ax.view_init(elev=el, azim=az); ax.set_axis_off()
    ax.set_title(title)
plt.savefig("glasses.png", dpi=120, bbox_inches="tight")
print("wrote glasses.png")
