"""Generate single-eye test frames (one rim each) for fit-testing lenses.

The main `frames.py` builds the full two-eye front; for a quick fit test you usually
just want one rim per eye. Run:

    python single_eye.py    ->  right_eye_frame.stl, left_eye_frame.stl

The left eye is the mirror of the right (lenses are mirror pairs). Swap INPUT_SVG /
OUTLINE_* for your own traced lens.
"""

import frames
from build123d import export_stl, mirror, Plane

# --- configure for your lens -------------------------------------------------
INPUT_SVG        = "examples/sample-lens.svg"  # your traced lens outline
OUTLINE_ROTATE   = 90.0    # rotate the trace to wearing (landscape) orientation
OUTLINE_WIDTH_MM = 55.5    # your measured lens width at its widest point
OPTICAL_CENTER   = None    # not needed for a single-eye fit test
WITH_LENS        = False    # also export reference lens STLs (these have a cosmetic
                            # null-triangulation warning -- they are NOT for printing)
# -----------------------------------------------------------------------------

face = frames.load_outline_svg(INPUT_SVG, OPTICAL_CENTER, OUTLINE_WIDTH_MM, OUTLINE_ROTATE)
frame = frames.build_frame(face)

right = frames.hinge_endpiece(frames.curve_rim(frame, 0))  # rim + temporal hinge pad
left = mirror(right, about=Plane.YZ)           # the other eye is its mirror

for name, part in (("right", right), ("left", left)):
    export_stl(part, f"{name}_eye_frame.stl")
    bb = part.bounding_box()
    print(f"wrote {name}_eye_frame.stl  ({bb.size.X:.1f} x {bb.size.Y:.1f} x "
          f"{bb.size.Z:.1f} mm, solids={len(part.solids())})")

if WITH_LENS:
    lens = frames.build_lens(face)
    export_stl(lens, "right_eye_lens.stl")
    export_stl(mirror(lens, about=Plane.YZ), "left_eye_lens.stl")
    print("wrote right_eye_lens.stl, left_eye_lens.stl")
