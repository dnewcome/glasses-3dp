"""
glasses-3dp — parametric SLA eyeglass frame generator (v2)

Manufacturing model:
  A real lens edge is ground with a FIXED-profile V bevel (a grinding wheel runs a
  constant V around the rim).  So the frame groove must be a fixed-profile V channel
  swept around the lens edge path -- constant width/angle, tilting only to follow the
  lens curvature.  Any extra edge thickness is "shoulder" hidden under the frame rim.

Pipeline:
  lens outline (parametric -> SVG)  ->
  lens blank (front/back spheres, meniscus)  ->
  groove tool (fixed V swept along the front-tracking apex path)  ->
  frame = rim blank  -  (lens + clearance)  -  groove tool   ->  STL / STEP

Coordinate system:
  - optical axis = Z; viewer looks toward -Z (lens front faces +Z)
  - front pole (optical center of front surface) at z = 0; lens body at z <= 0
"""

from build123d import *
import math

# ----------------------------------------------------------------------------
# Parameters
# ----------------------------------------------------------------------------

# Lens outline source.  Import a traced lens SVG, or fall back to the parametric
# rounded shape below (which is also exported as a tracing template).
INPUT_SVG        = None # e.g. "mylens.svg"; None -> parametric + write template
OUTLINE_ROTATE   = 0.0  # rotate the imported outline by this many degrees (e.g. 90 to
                        # turn a portrait-traced lens into landscape wearing orientation)
OUTLINE_WIDTH_MM = None # if set, scale the imported outline to this overall width (mm).
                        # Use for SVGs traced in pixels; leave None if already in mm.
OPTICAL_CENTER = None   # (x, y) mm of the optical center IN THE SVG FRAME; the outline
                        # is shifted so OC lands on the optical axis (origin), where the
                        # base/Rx spheres are centered.  None -> outline geometric center.

# Parametric fallback outline (silhouette), mm
LENS_WIDTH   = 52.0     # "A" box size, horizontal
LENS_HEIGHT  = 36.0     # "B" box size, vertical
CORNER_R     = 13.0     # corner rounding

# Prescription (sphere power, D) and chosen front base curve.
#   net power P = F_front + F_back -> F_back = P - base
#   lens clock reads diopters @ n=1.53, so geometry uses R = 530 / |D|
PRESCRIPTION_SPH = -2.0
BASE_DIOPTERS    = 6.0
BACK_DIOPTERS    = BASE_DIOPTERS - PRESCRIPTION_SPH      # -2.00 + (+6 base) -> -8 back
R_FRONT          = 530.0 / BASE_DIOPTERS                 # ~88.3 mm
R_BACK           = 530.0 / BACK_DIOPTERS                 # ~66.3 mm
CENTER_THICK     = 1.6

# Lens V bevel.  FRONT-SURFACE (base-curve) tracking:
#   front surface -> apex  = TRACK_DEPTH   (FIXED, the wheel rides off the base curve)
#   apex -> back surface   = varies         (edge thickness changes around the rim)
# The lens bevel is ASYMMETRIC (front flank fixed, back flank varies w/ Rx curvature).
TRACK_DEPTH    = 1.2     # fixed axial distance, front surface -> apex point, mm
BEVEL_PROTRUDE = 0.45    # apex protrusion past the lens surfaces, mm
BEVEL_STATIONS = 120     # bevel / groove sweep resolution around the rim

# Frame groove: a FIXED SYMMETRIC V (a rolled/ground channel), independent of the lens
# asymmetry.  The lens apex seats into it; its variable back flank just sits differently.
GROOVE_ANGLE   = 90.0    # symmetric apex angle of the frame groove, deg (sharper V)
GROOVE_CLEAR   = 0.10    # radial clearance at the groove bottom past the lens apex, mm
GROOVE_TOL     = 0.15    # axial widening of the groove for side clearance, mm

# Frame
RIM_WIDTH    = 2.5       # radial width of rim material outboard of the lens
LIP          = 1.0       # how far frame overlaps onto the lens face (front & back)
FRONT_PROUD  = 1.0       # frame front surface this far in +Z proud of the lens front
BACK_PROUD   = 1.5       # blank extends this far behind the lens back (trimmed by BACK_LIP)
LENS_TOL     = 0.10      # uniform clearance, lens vs frame (snap fit); undercut = PROTRUDE-TOL

# Frame cross-section: a slim shell of fixed depth following the FRONT base curve only.
# Prescription-INDEPENDENT: a strong Rx just makes a thick lens edge whose corners
# overhang the back of the frame (as in real frames) -- the frame never chases the Rx.
FRAME_THICK  = 4.0       # rim depth front-to-back along the base curve, mm

# Two-eye front + bridge
PD             = 62.0    # pupillary distance: separation of the two optical centers, mm
DECENTER       = 3.0     # OC nasal of the lens box center (parametric path), mm.
                         # Opens the nose: DBL = PD - LENS_WIDTH + 2*DECENTER.
                         # (For an imported lens this is implicit in OPTICAL_CENTER.)
BRIDGE_DROP    = 2.0     # bridge top this far below the lens top, mm
BRIDGE_H       = 8.0     # bridge vertical height, mm
BRIDGE_BACK    = 3.5     # bridge extends from the frame front to z = -BRIDGE_BACK, mm
BRIDGE_OVERLAP = 3.0     # how far the bridge reaches into each rim (to fuse), mm

OUT_DIR  = "."
SVG_PATH = "sample_lens.svg"
Z = Vector(0, 0, 1)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def sag(R, r):
    return R - math.sqrt(max(R * R - r * r, 0.0))


def outline_face():
    """Lens silhouette as a planar Face in the XY plane."""
    with BuildSketch() as sk:
        RectangleRounded(LENS_WIDTH, LENS_HEIGHT, CORNER_R)
    return sk.sketch.faces()[0]


def export_outline_svg(face, path):
    exp = ExportSVG(unit=Unit.MM)
    exp.add_shape(face)
    exp.write(path)


def load_outline_svg(path, optical_center=None, width_mm=None, rotate=0.0):
    """Import a traced lens outline and place its optical center at the origin (the
    optical axis), so the base/Rx spheres are correctly centered.  Optionally rotate
    (degrees) and scale to a target width (for SVGs traced in pixels / wrong orientation).

    The OC is what fixes pupillary distance: a pre-ground lens has a fixed OC, so you
    position the outline relative to it rather than to its geometric center.
    """
    shapes = import_svg(path, flip_y=True, align=None)   # preserve coordinates
    wires = [s for s in shapes if isinstance(s, Wire) and s.is_closed]
    if not wires:
        raise ValueError(f"no closed wire found in {path}")
    wire = max(wires, key=lambda w: w.length)            # largest closed loop = outline
    # flatten to a fine polyline: OCCT 2D-offset (rim/inset) fails on Bezier/spline
    # edges but is robust on line segments.
    n, L = 240, wire.length
    pts = [wire.position_at((i / n) * L, position_mode=PositionMode.LENGTH) for i in range(n)]
    wire = Polyline(*[(p.X, p.Y) for p in pts], close=True)
    face = make_face(wire).faces()[0]
    if rotate:
        face = Rot(0, 0, rotate) * face
        print(f"[svg ] rotated {rotate} deg")
    if width_mm:
        s = width_mm / face.bounding_box().size.X
        face = scale(face, by=s).faces()[0]
        print(f"[svg ] scaled x{s:.5f} -> outline width {width_mm} mm")
    bb = face.bounding_box()
    if optical_center is None:
        oc = ((bb.min.X + bb.max.X) / 2, (bb.min.Y + bb.max.Y) / 2)
        print(f"[svg ] no optical center given; using geometric center "
              f"({oc[0]:.1f}, {oc[1]:.1f}) -- PD/centering is approximate")
    else:
        oc = optical_center
        print(f"[svg ] optical center ({oc[0]:.1f}, {oc[1]:.1f}) -> optical axis")
    return Pos(-oc[0], -oc[1], 0) * face


def front_ball():
    return Pos(0, 0, -R_FRONT) * Sphere(R_FRONT)


def back_ball():
    return Pos(0, 0, -CENTER_THICK - R_BACK) * Sphere(R_BACK)


# Uniform ARC-LENGTH sampling of a wire.  Parameter-mode (`wire @ u`) jumps wildly at
# the wire's edge boundaries (e.g. 40mm steps), making degenerate/twisted loft segments
# -> gaps and uncut blocks.  LENGTH mode is uniform, but its argument is an ABSOLUTE
# distance, so scale u in [0,1] by the wire length.
def wire_pos(wire, u, length):
    return wire.position_at(u * length, position_mode=PositionMode.LENGTH)


def wire_tan(wire, u, length):
    return wire.tangent_at(u * length, position_mode=PositionMode.LENGTH)


def meniscus(face, inset=0.0):
    """Front/back spherical meniscus with a vertical edge at the outline (optionally
    inset).  inset=BEVEL_PROTRUDE gives the lens body without its bevel ridge (== the
    surfaces the frame lips rest on).  Uses the Rx back -- for the LENS model only."""
    src = face
    if inset:
        with BuildSketch() as s:
            add(face); offset(amount=-inset)
        src = s.sketch.faces()[0]
    return (extrude(src, amount=40, both=True) & front_ball()) - back_ball()


def seat_solid(face):
    """Prescription-INDEPENDENT lens seat: the front-surface cap over the inset outline,
    extruded straight back.  Differencing it from the frame gives the front lip seat plus
    a straight cavity the lens overhangs through -- the back (Rx) curve never enters the
    frame geometry."""
    with BuildSketch() as s:
        add(face); offset(amount=-BEVEL_PROTRUDE)
    inset = s.sketch.faces()[0]
    return extrude(inset, amount=40, both=True) & front_ball()


# ----------------------------------------------------------------------------
# Lens blank (meniscus; the real lens also carries a ground V bevel on its edge)
# ----------------------------------------------------------------------------

def build_lens(face):
    """Meniscus with a front-tracked V bevel ground onto the edge.

    Inner body uses the outline inset by BEVEL_PROTRUDE (so the front/back surfaces
    stop short of the silhouette); a swept ridge fills from that inset wall out to the
    apex.  Per station the ridge profile is a triangle:
        apex        = (outline point, front_z - TRACK_DEPTH)   <- fixed offset off front
        inner-front = (inset point,   front surface)
        inner-back  = (inset point,   back surface)            <- back leg varies w/ Rx
    """
    r_min = min(LENS_WIDTH, LENS_HEIGHT) / 2.0
    et_min = CENTER_THICK + sag(R_BACK, r_min) - sag(R_FRONT, r_min)
    if TRACK_DEPTH >= et_min:
        raise ValueError(f"TRACK_DEPTH {TRACK_DEPTH} exceeds thinnest edge {et_min:.2f}")
    print(f"[lens] front-track bevel: apex {TRACK_DEPTH}mm behind front, "
          f"protrude {BEVEL_PROTRUDE}mm; thinnest edge {et_min:.2f}mm")

    body = meniscus(face, inset=BEVEL_PROTRUDE)

    wire = face.outer_wire()
    wlen = wire.length
    n = BEVEL_STATIONS

    def tri(u):
        P = wire_pos(wire, u, wlen)
        t = wire_tan(wire, u, wlen)
        nrm = t.cross(Z)
        nrm = nrm.normalized() if nrm.length > 1e-9 else Vector(P.X, P.Y, 0).normalized()
        if nrm.dot(Vector(P.X, P.Y, 0)) < 0:
            nrm = -nrm
        r = math.hypot(P.X, P.Y)
        inx, iny = P.X - BEVEL_PROTRUDE * nrm.X, P.Y - BEVEL_PROTRUDE * nrm.Y
        ri = math.hypot(inx, iny)
        apex = (P.X, P.Y, -sag(R_FRONT, r) - TRACK_DEPTH)
        infront = (inx, iny, -sag(R_FRONT, ri))
        inback = (inx, iny, -CENTER_THICK - sag(R_BACK, ri))
        return make_face(Polyline(apex, infront, inback, close=True))

    tris = [tri(i / n) for i in range(n)]
    ridge = [loft([tris[i], tris[(i + 1) % n]], ruled=True) for i in range(n)]
    lens = body + Compound(ridge)
    return lens


# ----------------------------------------------------------------------------
# Frame groove: fixed SYMMETRIC V swept along the (front-tracked) lens apex line
# ----------------------------------------------------------------------------

def groove_tool(face):
    """Symmetric V channel the lens apex seats into.  Built like the lens bevel: sample
    the clean 2D outline, project the apex line onto the front sphere analytically, and
    make explicit 3D triangle profiles.  (Sampling the boolean-projected 3D wire instead
    fails -- its edges are stored out of order, giving 40mm jumps and uncut blocks.)

    Per station, in the radial(outward normal)/axial(Z) plane through the apex line:
        bottom = apex + GROOVE_CLEAR outward      (just past the lens apex)
        mouth  = apex - BEVEL_PROTRUDE inward, +/- width/2 axially  (at lens surface)
    """
    wire = face.outer_wire()
    wlen = wire.length
    depth = BEVEL_PROTRUDE + GROOVE_CLEAR
    width = 2 * depth * math.tan(math.radians(GROOVE_ANGLE / 2)) + GROOVE_TOL
    print(f"[groove] symmetric V: angle={GROOVE_ANGLE} depth={depth:.2f} "
          f"mouth={width:.2f} mm")
    n = BEVEL_STATIONS

    def prof(u):
        P = wire_pos(wire, u, wlen)
        t = wire_tan(wire, u, wlen)
        nrm = t.cross(Z)
        nrm = nrm.normalized() if nrm.length > 1e-9 else Vector(P.X, P.Y, 0).normalized()
        if nrm.dot(Vector(P.X, P.Y, 0)) < 0:
            nrm = -nrm
        r = math.hypot(P.X, P.Y)
        az = -sag(R_FRONT, r) - TRACK_DEPTH                # apex line z (front-tracked)
        bottom = (P.X + GROOVE_CLEAR * nrm.X, P.Y + GROOVE_CLEAR * nrm.Y, az)
        mx, my = P.X - BEVEL_PROTRUDE * nrm.X, P.Y - BEVEL_PROTRUDE * nrm.Y
        return make_face(Polyline(bottom, (mx, my, az + width / 2),
                                  (mx, my, az - width / 2), close=True))

    profs = [prof(i / n) for i in range(n)]
    return Compound([loft([profs[i], profs[(i + 1) % n]], ruled=True) for i in range(n)])


# ----------------------------------------------------------------------------
# Frame  (seat on the inset lens body; cut the symmetric groove)
# ----------------------------------------------------------------------------

def build_frame(face):
    with BuildSketch() as osk:
        add(face); offset(amount=RIM_WIDTH)
    with BuildSketch() as isk:
        add(face); offset(amount=-LIP)
    ring = osk.sketch - isk.sketch

    bb = face.bounding_box()
    r_max = math.hypot(max(abs(bb.min.X), abs(bb.max.X)),
                       max(abs(bb.min.Y), abs(bb.max.Y)))
    total_h = FRONT_PROUD + sag(R_FRONT, r_max) + FRAME_THICK + 2.0   # front-based, no Rx
    blank = extrude(Pos(0, 0, FRONT_PROUD) * ring, amount=-total_h)

    seat = scale(seat_solid(face), by=1.0 + LENS_TOL / r_max)
    print(f"[frame] seat clearance {LENS_TOL}mm; groove undercut "
          f"~{BEVEL_PROTRUDE - GROOVE_TOL / 2:.2f}mm")
    return (blank - seat) - groove_tool(face)


# ----------------------------------------------------------------------------
# Two-eye front + bridge
# ----------------------------------------------------------------------------

def build_bridge(face, right_frame, left_frame):
    """Solid bar spanning the nose gap, overlapping both rims so it fuses into one piece."""
    rb, lb = right_frame.bounding_box(), left_frame.bounding_box()
    x0 = lb.max.X - BRIDGE_OVERLAP        # reach into the left (nasal) rim
    x1 = rb.min.X + BRIDGE_OVERLAP        # reach into the right (nasal) rim
    top = face.bounding_box().max.Y       # lens top (outline is centered on OC=origin)
    y1, y0 = top - BRIDGE_DROP, top - BRIDGE_DROP - BRIDGE_H
    z1, z0 = FRONT_PROUD, -BRIDGE_BACK
    gap = (rb.min.X - lb.max.X)
    print(f"[bridge] nose gap (DBL) {gap:.1f} mm, bar x[{x0:.1f},{x1:.1f}] "
          f"y[{y0:.1f},{y1:.1f}]")
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * \
        Box(x1 - x0, y1 - y0, z1 - z0)


def curve_rim(frame, cx):
    """Place a single rim at optical center x=cx and bound it between two concentric
    FRONT-curve spheres (a slim shell of depth FRAME_THICK).  Prescription-independent:
    a thick (strong-Rx) lens edge simply overhangs the back."""
    proud = Pos(cx, 0, -R_FRONT) * Sphere(R_FRONT + FRONT_PROUD)
    inner = Pos(cx, 0, -R_FRONT) * Sphere(R_FRONT + FRONT_PROUD - FRAME_THICK)
    return ((Pos(cx, 0, 0) * frame) & proud) - inner


def build_front(face, lens, frame):
    """Mirror the eye to ±PD/2 and join with the bridge into one printable front."""
    # curve each rim per-eye BEFORE the bridge (per-eye spheres don't reach the nose).
    right_frame = curve_rim(frame, PD / 2)
    left_frame = mirror(right_frame, about=Plane.YZ)        # lands at -PD/2, mirror shape
    bridge = build_bridge(face, right_frame, left_frame)
    front = right_frame + left_frame + bridge

    right_lens = Pos(PD / 2, 0, 0) * lens
    left_lens = mirror(right_lens, about=Plane.YZ)
    print(f"[front] solids={len(front.solids())} (want 1), volume {front.volume:.1f} mm^3")
    return front, right_lens, left_lens


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def main():
    if INPUT_SVG:
        face = load_outline_svg(INPUT_SVG, OPTICAL_CENTER, OUTLINE_WIDTH_MM, OUTLINE_ROTATE)
        print(f"[svg ] loaded outline from {INPUT_SVG}")
    else:
        face = outline_face()
        try:
            export_outline_svg(face, SVG_PATH); print(f"[svg ] wrote template {SVG_PATH}")
        except Exception as e:
            print(f"[svg ] skipped ({e})")
        if DECENTER:                       # OC nasal of box center -> origin (optical axis)
            face = Pos(DECENTER, 0, 0) * face

    lens = build_lens(face)
    print(f"[lens] volume {lens.volume:.1f} mm^3, Z [{lens.bounding_box().min.Z:.2f}, "
          f"{lens.bounding_box().max.Z:.2f}]")
    frame = build_frame(face)

    front, right_lens, left_lens = build_front(face, lens, frame)
    export_stl(front, f"{OUT_DIR}/front.stl")
    export_stl(right_lens, f"{OUT_DIR}/lens_right.stl")
    export_stl(left_lens, f"{OUT_DIR}/lens_left.stl")

    try:
        export_step(Compound([front, right_lens, left_lens]),
                    f"{OUT_DIR}/assembly.step")
        print("[step] wrote assembly.step")
    except Exception as e:
        print(f"[step] skipped ({e})")
    print("[done] wrote front.stl, lens_right.stl, lens_left.stl")


if __name__ == "__main__":
    main()
