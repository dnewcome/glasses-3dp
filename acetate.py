"""Classic plastic (acetate) eyeglasses in the Wayfarer / Warby Parker idiom, built for
this lens shape: bold rims, a heavy brow, a chunky keyhole bridge, flared endpieces, and
separate thick temple arms that bolt on with the user's screw hinges.

Run:
    python acetate.py   ->  acetate_front.stl, temple_right.stl, temple_left.stl

It reuses the functional core in frames.py (lens groove/seat, base-curve shell, back hinge
pad) but overrides the styling parameters to the bold acetate look.  Swap INPUT_SVG /
OUTLINE_* for your own lens.
"""

import math
import frames
from build123d import *

# --- lens source -------------------------------------------------------------
# The user's ACTUAL lens (round, 55.5mm) -- the opening/groove must fit this so the real
# lens snaps in.  The Wayfarer reference (farer-outline.png) informs the STYLING only
# (bold rim, heavy brow, keyhole bridge, flared endpieces, temples), not the lens shape.
INPUT_SVG        = "examples/sample-lens.svg"
OUTLINE_ROTATE   = 90.0
OUTLINE_WIDTH_MM = 55.5
OPTICAL_CENTER   = None

# --- bold acetate styling: override the slim frames.py defaults ---------------
frames.RIM_WIDTH   = 5.0     # bold rim outboard of the lens; lands front ~140mm wide
frames.LIP         = 1.6     # acetate overlaps further onto the lens face
frames.FRAME_THICK = 6.0     # thick front plate front-to-back (was 4)
frames.FRONT_PROUD = 1.5     # front stands proud of the lens front

# brow: extra rim height across the top (the heavy Wayfarer browline)
BROW_EXTRA       = 5.5       # extra rim width added on top, mm
BROW_START_FRAC  = 0.45      # brow applies above this fraction of lens height (0=bottom,1=top)
BROW_BLEND       = 6.0       # horizontal taper of the brow ends toward the temples, mm

# keyhole bridge
BRIDGE_W         = 7.0       # bridge bar thickness top-to-bottom at the nose, mm
BRIDGE_TOPDROP   = 1.0       # bridge top this far below the lens top, mm
KEYHOLE_R        = 5.5       # nose keyhole radius, mm
KEYHOLE_DROP     = 2.0       # keyhole center below the bridge top, mm

# rounded acetate front edges
EDGE_FILLET      = 0.0       # 3D fillet disabled (non-manifold); rounding via swept profile TODO

# --- temples -----------------------------------------------------------------
TEMPLE_LEN       = 135.0     # straight shaft length before the ear bend, mm
TEMPLE_W         = 7.0       # temple vertical height (matches endpiece), mm
TEMPLE_T         = 4.5       # temple thickness (sideways), mm
TEMPLE_EAR_LEN   = 38.0      # length of the down-curved earpiece, mm
TEMPLE_EAR_ANG   = 32.0      # earpiece bend-down angle, deg
TEMPLE_TAPER     = 0.8       # earpiece end scale (taper toward the tip)
# -----------------------------------------------------------------------------

R_FRONT = frames.R_FRONT
sag = frames.sag


# ----------------------------------------------------------------------------
# Bold front
# ----------------------------------------------------------------------------

def brow_sketch(face):
    """2D crescent of extra material across the top of the rim (the heavy browline).
    Kept as a planar sketch so it unions into the outer outline in 2D -- a 3D union of a
    separately-extruded brow leaves a non-manifold seam where it touches the ring."""
    bb = face.bounding_box()
    with BuildSketch() as wide:
        add(face); offset(amount=frames.RIM_WIDTH + BROW_EXTRA, kind=Kind.INTERSECTION)
    with BuildSketch() as base:
        add(face); offset(amount=frames.RIM_WIDTH, kind=Kind.INTERSECTION)
    crescent = wide.sketch - base.sketch
    ybrow = bb.min.Y + (bb.max.Y - bb.min.Y) * BROW_START_FRAC
    span = (bb.max.X - bb.min.X) + 2 * (frames.RIM_WIDTH + BROW_EXTRA) + 20
    high = bb.max.Y + BROW_EXTRA + 10
    with BuildSketch() as topmask:
        with Locations(((bb.min.X + bb.max.X) / 2, (ybrow + high) / 2)):
            Rectangle(span, high - ybrow)
    return crescent & topmask.sketch


def acetate_eye_flat(face):
    """Bold rim (rim + brow fused in 2D), seat + groove cut, still flat (pre-curve).
    Building the whole outer outline in 2D, then extruding once, keeps it a single solid
    (no 3D union seam) -- the watertight way to add the brow."""
    with BuildSketch() as osk:
        add(face); offset(amount=frames.RIM_WIDTH, kind=Kind.INTERSECTION)
    outer = osk.sketch + brow_sketch(face)            # 2D union -- robust
    with BuildSketch() as isk:
        add(face); offset(amount=-frames.LIP, kind=Kind.INTERSECTION)
    ring = outer - isk.sketch

    bb = face.bounding_box()
    r_max = math.hypot(max(abs(bb.min.X), abs(bb.max.X)),
                       max(abs(bb.min.Y), abs(bb.max.Y)))
    total_h = frames.FRONT_PROUD + sag(R_FRONT, r_max) + frames.FRAME_THICK + 2.0
    blank = extrude(Pos(0, 0, frames.FRONT_PROUD) * ring, amount=-total_h)
    seat = scale(frames.seat_solid(face), by=1.0 + frames.LENS_TOL / r_max)
    return (blank - seat) - frames.groove_tool(face)


def round_front_edge(solid):
    """Fillet the proud front edges for the pillowed acetate look.  Filleting the whole
    shell is fragile; the front-face zone (top 0.6mm of the shell) rounds reliably."""
    if not EDGE_FILLET:
        return solid
    zmax = solid.bounding_box().max.Z
    edges = solid.edges().filter_by_position(Axis.Z, zmax - 0.6, zmax + 0.1)
    for r in (EDGE_FILLET, 0.7, 0.5, 0.3):       # tight Wayfarer corners need a retry
        try:
            out = fillet(edges, r)
            print(f"[acetate] rounded {len(edges)} front edges r={r}")
            return out
        except Exception:
            continue
    print("[acetate] front-edge fillet skipped (OCCT)")
    return solid


def keyhole_nose(face, front):
    """A classic keyhole bridge: a clean round notch at the top center of the nose.  With
    this lens at this PD the DBL is tiny (~6.5mm), so the cut is sized to stay clear of
    the lens openings -- it carves the keyhole without exposing the nasal lens groove."""
    fb = front.bounding_box()
    # right lens opening nasal edge = how close the cut may come to center (lens-safe)
    with BuildSketch() as isk:
        add(face); offset(amount=-frames.LIP, kind=Kind.INTERSECTION)
    gap_half = (Pos(frames.PD / 2, 0, 0) * isk.sketch.faces()[0]).bounding_box().min.X
    r = min(KEYHOLE_R, gap_half - 0.6)
    top = face.bounding_box().max.Y
    yc = top - BRIDGE_TOPDROP - r - 0.5               # notch sits just under the brow top
    with BuildSketch() as sk:
        with Locations((0, yc)):
            Circle(r)
    cut = extrude(sk.sketch, amount=fb.max.Z + 10, both=True)
    print(f"[bridge] keyhole notch r={r:.1f} at y={yc:.1f} (gap_half={gap_half:.1f}, lens-safe)")
    return front - cut


def build_acetate_front(face):
    flat = acetate_eye_flat(face)
    right = frames.hinge_endpiece(frames.curve_rim(flat, frames.PD / 2), frames.PD / 2)
    left = mirror(right, about=Plane.YZ)
    front = right + left                              # bold rims overlap -> fused nose web
    front = keyhole_nose(face, front)
    front = round_front_edge(front)
    print(f"[front] solids={len(front.solids())} (want 1), volume {front.volume:.0f} mm^3")
    return front


# ----------------------------------------------------------------------------
# Temple arm (separate printable part; bolts to the endpiece with the screw hinge)
# ----------------------------------------------------------------------------

TEMPLE_SCREW_SP  = 3.0       # pilot-hole spacing on the temple pad, mm
TEMPLE_SCREW_D   = 0.9       # pilot-hole diameter, mm
TEMPLE_HOLE_DEP  = 3.5       # pilot-hole depth, mm


def build_temple():
    """A thick acetate temple in its own frame: front mounting face at z=0 (normal +Z,
    meets the hinge), shaft running back along -Z, then a down-curved earpiece.  Two pilot
    holes in the front face take the hinge's temple leaf.  Built for the right side; the
    left is its mirror."""
    w, t, L = TEMPLE_W, TEMPLE_T, TEMPLE_LEN
    shaft = Pos(0, 0, -L / 2) * Box(t, w, L)
    # earpiece: pivot at the shaft end (z=-L), rotate down about X, extend further back
    earL = TEMPLE_EAR_LEN
    ear = Pos(0, 0, -L) * Rot(-TEMPLE_EAR_ANG, 0, 0) * (Pos(0, 0, -earL / 2) * Box(t, w, earL))
    temple = shaft + ear

    # round the long edges for the acetate feel
    try:
        longE = temple.edges().filter_by(Axis.Z) + temple.edges().group_by(Axis.Z)[-1] \
            + temple.edges().group_by(Axis.Z)[0]
        temple = fillet(temple.edges().filter_by(Axis.Z), min(t, w) / 2 - 0.4)
    except Exception as e:
        print(f"[temple] edge fillet skipped ({type(e).__name__})")

    # two pilot holes bored into the front face (z=0), along the vertical (Y)
    for dy in (TEMPLE_SCREW_SP / 2, -TEMPLE_SCREW_SP / 2):
        temple = temple - (Pos(0, dy, -TEMPLE_HOLE_DEP / 2 + 0.1)
                           * Cylinder(TEMPLE_SCREW_D / 2, TEMPLE_HOLE_DEP + 0.2))
    print(f"[temple] {L}mm shaft + {earL}mm earpiece @ {TEMPLE_EAR_ANG}deg, "
          f"{t}x{w}mm acetate, solids={len(temple.solids())}")
    return temple


def main():
    face = frames.load_outline_svg(INPUT_SVG, OPTICAL_CENTER, OUTLINE_WIDTH_MM, OUTLINE_ROTATE)
    front = build_acetate_front(face)
    export_stl(front, "acetate_front.stl")
    bb = front.bounding_box()
    print(f"wrote acetate_front.stl  ({bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm)")

    temple = build_temple()
    export_stl(temple, "temple_right.stl")
    export_stl(mirror(temple, about=Plane.YZ), "temple_left.stl")
    tb = temple.bounding_box()
    print(f"wrote temple_right.stl, temple_left.stl  "
          f"({tb.size.X:.1f} x {tb.size.Y:.1f} x {tb.size.Z:.1f} mm each)")

    # combined assembled view -- temples mounted at the endpieces, opened.  This is for
    # looking at / inspecting the whole pair; PRINT THE 3 PARTS SEPARATELY (flat), as they
    # join via the screw hinges -- this assembly is one mesh in the worn pose, not a print.
    fb = front.bounding_box()
    px, pz = fb.max.X - 3.0, fb.min.Z + 2.0
    splay = 7.0
    asmR = Pos(px, 0, pz) * Rot(0, splay, 0) * temple
    asmL = Pos(-px, 0, pz) * Rot(0, -splay, 0) * mirror(temple, about=Plane.YZ)
    export_stl(Compound([front, asmR, asmL]), "glasses.stl")
    gb = Compound([front, asmR, asmL]).bounding_box()
    print(f"wrote glasses.stl  (assembled view, {gb.size.X:.0f} x {gb.size.Y:.0f} x "
          f"{gb.size.Z:.0f} mm; print the 3 parts separately)")


if __name__ == "__main__":
    main()
