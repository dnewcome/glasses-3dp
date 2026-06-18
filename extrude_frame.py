"""Outline-driven glasses (composite): keep a Wayfarer OUTER silhouette but cut the lens
openings to the user's ACTUAL lens outline, sized so the real lens fits with proper rims
and a real nose gap.  Then extrude.

    python extrude_frame.py   ->  frame_front.stl  (+ render frame.png)

Approach the user asked for: import outlines -> place -> subtract -> extrude.  No frame is
derived from placing one lens at the PD, so the nose has room.  Grooves / hinges / temples
are layered on after the shape + fit are right.
"""
import math
import frames
from build123d import *

# --- outer shape (style) -----------------------------------------------------
OUTER_SVG   = "examples/wayfarer-frame.svg"   # its outer silhouette = the frame style

# --- lens openings (fit the real lens) ---------------------------------------
LENS_SVG    = "examples/sample-lens.svg"
LENS_ROTATE = 270.0         # orient the trace to wearing position (rot90 was upside-down)
LENS_WIDTH  = 55.5          # the user's lens width, mm
DBL         = 16.0          # nose gap between the lens openings, mm (room for the nose)

# --- rims / brow (how much outer around the openings) ------------------------
RIM_SIDE    = 8.0           # temporal rim, mm
RIM_TOP     = 9.0           # brow (top rim), mm
RIM_BOT     = 10.0          # bottom rim, mm (round lens needs room low at the eye line)
THICK       = 6.0           # front-to-back extrusion depth, mm
SQUASH_BOT  = 0.80          # scale everything below the eye line by this in Y (1.0 = off)

# --- lens groove (retention): SAME method/keying as the test lens (frames.py groove_tool):
# a symmetric V keyed to the lens bevel.  Mouth at the lens surface (outline-BEVEL_PROTRUDE),
# bottom GROOVE_CLEAR past the apex (outline), width from the bevel depth + angle.
BEVEL_PROTRUDE= 0.50        # how far the lens bevel apex protrudes past its surfaces, mm
BASE_DIOPTERS = 6.0         # lens front base curve (lens-clock diopters) -> R = 530/D.  The
                            # groove apex line curves with this sphere's sag, like the lens.
GROOVE_ANGLE  = 90.0        # symmetric V apex angle, deg
GROOVE_CLEAR  = 0.30        # groove bottom this far past the lens apex, mm (deeper channel)
GROOVE_TOL    = 0.15        # axial widening for side clearance, mm
GROOVE_MERGE  = 0.50        # mouth reaches this far inside the opening wall (overlap, not
                            # coincide -- coincident faces wreck the boolean)
GROOVE_STN    = 220         # stations swept around each lens
# groove depth past the opening wall = BEVEL_PROTRUDE + GROOVE_CLEAR = 0.80mm (test print
# was 0.55mm); the opening/seat is inset by the full BEVEL_PROTRUDE, like frames.py.
LENS_TOL      = 0.25        # radial clearance: the ENTIRE lens cavity (opening + groove) is
                            # grown by this so the real lens drops in.  A thick stiff frame
                            # won't flex like the thin test print, and SLA shrinks the hole
                            # undersize -- RAISE if the lens is tight, lower if it rattles.
                            # (Grows opening AND groove together, so groove depth is kept.)

# --- face form: gentle horizontal wrap toward the temples (about a vertical axis) --------
FACE_FORM_R   = 700.0       # wrap radius, mm (0 = flat).  ~700 -> a few deg of wrap

# --- hinges (screw-on, into the back of each temporal corner) ----------------
HINGE_Y       = 22.0        # screw-pad / temple center height -- up at the top-temporal tab
                            # (the little flares that stick out)
HINGE_INSET   = 5.0         # temple this far in from the temporal edge, mm (= temple midpoint)
# The hinge's front leaf screws to the endpiece inboard of the temple; these two pilots are
# measured in from the temple MIDPOINT.
HINGE_HOLE1   = 5.5         # first pilot, mm in from the temple midpoint
HINGE_HOLE2   = 8.5         # second pilot, mm in from the temple midpoint
HINGE_SCREW_D = 0.9         # pilot hole diameter, mm
HINGE_SCREW_SP= 3.0         # spacing for the temple's own mating pilots, mm
HINGE_HOLE_DEP= 4.0         # pilot hole depth into the back of the frame, mm

# --- temples (separate printable arms) ---------------------------------------
TEMPLE_LEN    = 125.0       # straight shaft length, mm
TEMPLE_W      = 7.0         # temple vertical height, mm
TEMPLE_T      = 4.5         # temple thickness (sideways), mm
TEMPLE_EAR_LEN= 38.0        # down-curved earpiece length, mm
TEMPLE_EAR_ANG= 32.0        # earpiece bend-down angle, deg
# -----------------------------------------------------------------------------
Z = Vector(0, 0, 1)


def load_outer_fitted(path, target_w, target_h):
    """The frame's outer silhouette (Wayfarer), flattened to a polyline and scaled
    (non-uniformly) to the target width/height, centered on origin.  Flattening + scaling
    the POINTS (not the Face) is essential: a non-uniformly scaled imported Face is planar
    but silently refuses boolean cuts."""
    shapes = import_svg(path, flip_y=True, align=None)
    f = max([s for s in shapes if isinstance(s, Face)], key=lambda f: f.area)
    wire = f.outer_wire()
    n, L = 360, wire.length
    pts = [wire.position_at(i / n * L, position_mode=PositionMode.LENGTH) for i in range(n)]
    xs = [p.X for p in pts]
    ys = [p.Y for p in pts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    sx, sy = target_w / (max(xs) - min(xs)), target_h / (max(ys) - min(ys))
    scaled = [((p.X - cx) * sx, (p.Y - cy) * sy) for p in pts]
    return make_face(Polyline(*scaled, close=True)).faces()[0]


def squash_bottom(face, factor, y0=0.0):
    """Scale everything below y0 by `factor` in Y (anchored at y0), keeping the X profile.
    Works on the polyline points of the outer + hole wires so the boolean stays clean."""
    def sq(w):
        n, L = max(160, int(w.length)), w.length
        pts = [w.position_at(i / n * L, position_mode=PositionMode.LENGTH) for i in range(n)]
        flat = [(p.X, y0 + (p.Y - y0) * factor if p.Y < y0 else p.Y) for p in pts]
        return make_face(Polyline(*flat, close=True))
    outer_f = sq(face.outer_wire())                 # build faces OUTSIDE the sketch context
    hole_fs = [sq(iw) for iw in face.inner_wires()]
    with BuildSketch() as sk:
        add(outer_f)
        for hf in hole_fs:
            add(hf, mode=Mode.SUBTRACT)
    return sk.sketch.faces()[0]


def mid_z(x):
    """Z of the wrapped mid-surface at horizontal position x (THICK/2 when flat)."""
    if not FACE_FORM_R:
        return THICK / 2
    Rm = FACE_FORM_R - THICK / 2
    return (THICK - FACE_FORM_R) + math.sqrt(Rm * Rm - x * x)


def groove_tool(lens_face):
    """Symmetric V groove swept around the lens edge, keyed to the lens bevel exactly like
    frames.py groove_tool: mouth at the lens surface (apex - BEVEL_PROTRUDE), bottom
    GROOVE_CLEAR past the apex, width from the bevel depth + angle.  Sampled on the clean
    2D outline, one fused multi-section loft.

    The apex line CURVES with the lens front base curve: az dips by sag(R_FRONT, r) where r
    is the distance from the lens optical centre -- so the groove matches the real lens's
    spherical-edge groove (centred in the frame; the overall face-form wrap adds mid_z)."""
    w = lens_face.outer_wire()
    L, n = w.length, GROOVE_STN
    c = lens_face.center()
    R = 530.0 / BASE_DIOPTERS
    depth = BEVEL_PROTRUDE + GROOVE_CLEAR
    width = 2 * depth * math.tan(math.radians(GROOVE_ANGLE / 2)) + GROOVE_TOL

    Ps = [w.position_at(i / n * L, position_mode=PositionMode.LENGTH) for i in range(n)]
    sags = [R - math.sqrt(max(R * R - ((p.X - c.X) ** 2 + (p.Y - c.Y) ** 2), 0.0)) for p in Ps]
    sag_mean = sum(sags) / len(sags)                           # centre the curved groove

    def prof(i):
        P, sagv = Ps[i], sags[i]
        t = w.tangent_at(i / n * L, position_mode=PositionMode.LENGTH)
        nrm = t.cross(Z)
        nrm = nrm.normalized() if nrm.length > 1e-9 else Vector(P.X - c.X, P.Y - c.Y, 0).normalized()
        if nrm.dot(Vector(P.X - c.X, P.Y - c.Y, 0)) < 0:
            nrm = -nrm
        az = mid_z(P.X) - (sagv - sag_mean)                    # base-curve dip + face-form
        mo = BEVEL_PROTRUDE + GROOVE_MERGE                      # mouth overlaps into the hole
        mx, my = P.X - mo * nrm.X, P.Y - mo * nrm.Y             # mouth at the lens surface
        bx, by = P.X + GROOVE_CLEAR * nrm.X, P.Y + GROOVE_CLEAR * nrm.Y  # bottom, past apex
        return make_face(Polyline((mx, my, az + width / 2), (bx, by, az),
                                  (mx, my, az - width / 2), close=True))

    profs = [prof(i) for i in range(n)]
    return loft(profs + [profs[0]], ruled=True)


def hinge_holes(front):
    """Bore two screw pilot holes into the BACK (z=0) of each temporal corner, where the
    hinge's front leaf screws on.  Built at the right corner, mirrored to the left."""
    bb = front.bounding_box()
    xc = bb.max.X - HINGE_INSET                                # temple midpoint (x)
    holes = []
    for sgn in (1, -1):                                        # right (+x) and left (-x)
        for off in (HINGE_HOLE1, HINGE_HOLE2):                 # measured in from the midpoint
            x = sgn * (xc - off)
            bz = mid_z(x) - THICK / 2                          # back surface at this x
            holes.append(Pos(x, HINGE_Y, bz + HINGE_HOLE_DEP / 2 - 0.1)
                         * Cylinder(HINGE_SCREW_D / 2, HINGE_HOLE_DEP + 0.2))
    out = front
    for h in holes:
        out = out - h
    print(f"[hinge] front-leaf pilots at x=+/-{xc-HINGE_HOLE1:.1f} & +/-{xc-HINGE_HOLE2:.1f} "
          f"({HINGE_HOLE1}/{HINGE_HOLE2}mm in from temple midpoint {xc:.1f}), y={HINGE_Y}, back")
    return out


def build_temple():
    """A thick acetate temple in its own frame: front mounting face at z=0 (+Z, meets the
    hinge), shaft back along -Z, then a down-curved earpiece.  Right side; mirror for left."""
    w, t, L = TEMPLE_W, TEMPLE_T, TEMPLE_LEN
    shaft = Pos(0, 0, -L / 2) * Box(t, w, L)
    earL = TEMPLE_EAR_LEN
    ear = Pos(0, 0, -L) * Rot(-TEMPLE_EAR_ANG, 0, 0) * (Pos(0, 0, -earL / 2) * Box(t, w, earL))
    temple = shaft + ear
    for dy in (HINGE_SCREW_SP / 2, -HINGE_SCREW_SP / 2):       # mate holes in the front face
        temple = temple - (Pos(0, dy, -HINGE_HOLE_DEP / 2 + 0.1)
                           * Cylinder(HINGE_SCREW_D / 2, HINGE_HOLE_DEP + 0.2))
    print(f"[temple] {L}mm shaft + {earL}mm earpiece @ {TEMPLE_EAR_ANG}deg, {t}x{w}mm")
    return temple


def main():
    # the user's lens, oriented + handed for each eye
    lens = frames.load_outline_svg(LENS_SVG, None, LENS_WIDTH, LENS_ROTATE)
    lens = mirror(lens, about=Plane.YZ).faces()[0]   # handedness; coerce Sketch -> Face
    lb = lens.bounding_box()
    eye_dx = lb.size.X / 2 + DBL / 2                 # geometric-center spacing
    right_lens = (Pos(eye_dx, 0, 0) * lens).faces()[0]
    left_lens = mirror(right_lens, about=Plane.YZ).faces()[0]

    # grow the lens outline by LENS_TOL: the whole cavity (opening + groove) is built from
    # this, so the real lens drops in with clearance while the groove keeps its full depth.
    def grow(face, amt):
        with BuildSketch() as s:
            add(face); offset(amount=amt, kind=Kind.INTERSECTION)
        return s.sketch.faces()[0]
    right_cav = grow(right_lens, LENS_TOL)
    left_cav = grow(left_lens, LENS_TOL)

    # the see-through opening = the lens SURFACE (cavity inset by the full bevel flank);
    # the apex itself is held in the groove (as in frames.py).
    def surface_opening(cav):
        with BuildSketch() as ok:
            add(cav); offset(amount=-BEVEL_PROTRUDE, kind=Kind.INTERSECTION)
        return ok.sketch.faces()[0]
    right_op, left_op = surface_opening(right_cav), surface_opening(left_cav)

    # size the outer silhouette to wrap the openings with the target rims
    need_w = 2 * eye_dx + lb.size.X + 2 * RIM_SIDE
    need_h = lb.size.Y + RIM_TOP + RIM_BOT
    outer = load_outer_fitted(OUTER_SVG, need_w, need_h)
    outer = Pos(0, (RIM_TOP - RIM_BOT) / 2, 0) * outer
    if SQUASH_BOT != 1.0:                            # squash outer ONLY (lens shape intact)
        outer = squash_bottom(outer, SQUASH_BOT, y0=0.0)

    with BuildSketch() as sk:
        add(outer)
        add(right_op, mode=Mode.SUBTRACT)
        add(left_op, mode=Mode.SUBTRACT)
    frame_face = sk.sketch.faces()[0]

    if FACE_FORM_R:                                  # face-form wrap: extrude tall, bound
        sag = FACE_FORM_R - math.sqrt(FACE_FORM_R**2 - (need_w / 2 + 5)**2)
        block = extrude(frame_face, amount=THICK + sag + 4, both=True)
        ax_z = THICK - FACE_FORM_R
        proud = Pos(0, 0, ax_z) * Rot(90, 0, 0) * Cylinder(FACE_FORM_R, 400)
        inner = Pos(0, 0, ax_z) * Rot(90, 0, 0) * Cylinder(FACE_FORM_R - THICK, 400)
        front = (block & proud) - inner
        print(f"[wrap] face-form R={FACE_FORM_R}mm, temporal sweep-back {sag:.1f}mm")
    else:
        front = extrude(frame_face, amount=THICK)

    # lens retention groove (bevel-keyed, on the grown cavity) + hinge pilot holes
    front = front - groove_tool(right_cav) - groove_tool(left_cav)
    front = hinge_holes(front)

    export_stl(front, "frame_front.stl")
    temple = build_temple()
    export_stl(temple, "temple_right.stl")
    export_stl(mirror(temple, about=Plane.YZ), "temple_left.stl")

    # combined assembled view (temples opened) -- print the 3 parts separately
    bbf = front.bounding_box()
    px = bbf.max.X - HINGE_INSET
    pz = mid_z(px) - THICK / 2                        # back surface at the tab
    asmR = Pos(px, HINGE_Y, pz) * Rot(0, 7, 0) * temple
    asmL = Pos(-px, HINGE_Y, pz) * Rot(0, -7, 0) * mirror(temple, about=Plane.YZ)
    export_stl(Compound([front, asmR, asmL]), "glasses.stl")

    bb = front.bounding_box()
    print(f"[frame] lens {lb.size.X:.1f}x{lb.size.Y:.1f}mm, DBL {DBL}mm, "
          f"eye-centers +/-{eye_dx:.1f}mm, effective PD ~{2*eye_dx-9.5:.0f}mm")
    print(f"[frame] front {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm, "
          f"solids={len(front.solids())}")


if __name__ == "__main__":
    main()
