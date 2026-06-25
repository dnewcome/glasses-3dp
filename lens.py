"""Round lens blank generator -- a parametric meniscus from a prescription.

Makes a simple ROUND lens: front base-curve sphere, prescription back curve, circular
edge -- as a watertight solid to print in clear resin and post-process by hand (sand,
polish, edge to a frame).  A round blank is the easiest shape to chuck up and finish, so
this is intentionally decoupled from any frame outline.

    python lens.py        ->  lens.stl

Optics reused from frames.py:
    R_front = 530 / BASE_DIOPTERS              (lens-clock convention, n=1.53)
    back    = BASE_DIOPTERS - PRESCRIPTION_SPH  ->  R_back = 530 / back
A minus Rx gives a meniscus with a thicker edge than center (as here, -2.00 D).

This is the seed of the eventual full parametric-Rx lens; sphere only for now
(cylinder / axis for astigmatism is TODO -> a toric back surface).
"""
import math
import struct

import frames
from build123d import BuildSketch, Circle, export_stl

# --- prescription + blank ----------------------------------------------------
BASE_DIOPTERS    = 6.0     # front base curve (lens-clock D); R_front = 530 / base
PRESCRIPTION_SPH = -2.0    # sphere power (D); back curve = base - Rx  (demo lens)
CENTER_THICK     = 2.0     # center thickness, mm (a touch thick for a printable blank)
LENS_DIAMETER    = 60.0    # round blank diameter, mm (covers a ~55.5mm lens; grind down)
EDGE_BEVEL       = False   # True -> grind a V bevel onto the edge; False -> plain edge
# -----------------------------------------------------------------------------

# Drive frames.py's optics with these values.  Its R_FRONT/R_BACK are module globals
# computed at import from the defaults, so set them (and the diopters) explicitly.
frames.BASE_DIOPTERS    = BASE_DIOPTERS
frames.PRESCRIPTION_SPH = PRESCRIPTION_SPH
frames.BACK_DIOPTERS    = BASE_DIOPTERS - PRESCRIPTION_SPH
frames.R_FRONT          = 530.0 / BASE_DIOPTERS
frames.R_BACK           = 530.0 / frames.BACK_DIOPTERS
frames.CENTER_THICK     = CENTER_THICK
frames.LENS_WIDTH = frames.LENS_HEIGHT = LENS_DIAMETER   # build_lens edge-thickness check


def clean_stl(path, weld=1e-5):
    """Weld coincident vertices and drop degenerate (zero-area) triangles, then rewrite.
    A spherical surface has a pole singularity on the optical axis; OCCT's mesher emits a
    fan of zero-area slivers there (a real STL defect, non-manifold even at high precision).
    The lens has two such poles (front + back, at the lens center) -- this removes them so
    the file is watertight for any slicer.  Returns (#tris, #non-manifold edges)."""
    with open(path, "rb") as f:
        f.read(80)
        (n,) = struct.unpack("<I", f.read(4))
        raw = [struct.unpack("<12f", f.read(50)[:48]) for _ in range(n)]
    tris = [((v[3], v[4], v[5]), (v[6], v[7], v[8]), (v[9], v[10], v[11])) for v in raw]

    canon = {}                                          # weld near-coincident vertices
    def w(p):
        k = (round(p[0] / weld), round(p[1] / weld), round(p[2] / weld))
        return canon.setdefault(k, p)

    kept = []
    for a, b, c in tris:
        a, b, c = w(a), w(b), w(c)
        if a == b or b == c or a == c:
            continue                                    # two verts coincide -> degenerate
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        L = math.sqrt(nx * nx + ny * ny + nz * nz)
        if L < 1e-9:
            continue                                    # zero-area sliver
        kept.append((nx / L, ny / L, nz / L, a, b, c))

    with open(path, "wb") as f:
        f.write(b"\0" * 80)
        f.write(struct.pack("<I", len(kept)))
        for nx, ny, nz, a, b, c in kept:
            f.write(struct.pack("<12f", nx, ny, nz, *a, *b, *c))
            f.write(b"\0\0")

    edges = {}
    for _, _, _, a, b, c in kept:
        for u, v in ((a, b), (b, c), (c, a)):
            e = (u, v) if u <= v else (v, u)
            edges[e] = edges.get(e, 0) + 1
    return len(kept), sum(1 for cnt in edges.values() if cnt != 2)


def main():
    with BuildSketch() as sk:
        Circle(LENS_DIAMETER / 2)
    face = sk.sketch.faces()[0]

    # meniscus() = front/back spheres on the round outline (plain vertical edge);
    # build_lens() adds the front-tracked V bevel for a frame groove.
    lens = frames.build_lens(face) if EDGE_BEVEL else frames.meniscus(face)

    export_stl(lens, "lens.stl")
    ntri, leaks = clean_stl("lens.stl")          # remove sphere-pole slivers -> watertight

    r = LENS_DIAMETER / 2
    edge = CENTER_THICK + frames.sag(frames.R_BACK, r) - frames.sag(frames.R_FRONT, r)
    bb = lens.bounding_box()
    print(f"wrote lens.stl  round D{LENS_DIAMETER:.0f}mm, base {BASE_DIOPTERS:.1f}D / "
          f"Rx {PRESCRIPTION_SPH:+.2f}D, center {CENTER_THICK:.1f}mm, edge ~{edge:.1f}mm"
          f"{' (+V bevel)' if EDGE_BEVEL else ''}")
    print(f"  bbox {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm, "
          f"solids={len(lens.solids())}, volume {lens.volume:.0f} mm^3")
    print(f"  mesh cleaned: {ntri} triangles, "
          f"{'WATERTIGHT' if leaks == 0 else f'{leaks} non-manifold edges'}")


if __name__ == "__main__":
    main()
