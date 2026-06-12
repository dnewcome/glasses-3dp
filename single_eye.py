"""Generate a single-eye frame STL for test-printing one lens.

The main `frames.py` builds the full two-eye front; for a quick fit test you usually
just want ONE rim. Configure your lens below and run:

    python single_eye.py        ->  right_eye_frame.stl  (+ right_eye_lens.stl)

Swap INPUT_SVG / OUTLINE_* for your own traced lens.
"""

import frames
from build123d import export_stl

# --- configure for your lens -------------------------------------------------
INPUT_SVG        = "examples/sample-lens.svg"  # your traced lens outline
OUTLINE_ROTATE   = 90.0    # rotate the trace to wearing (landscape) orientation
OUTLINE_WIDTH_MM = 55.5    # your measured lens width at its widest point
OPTICAL_CENTER   = None    # not needed for a single-eye fit test
WITH_LENS        = True     # also export the modeled lens (for reference/preview)
# -----------------------------------------------------------------------------

face = frames.load_outline_svg(INPUT_SVG, OPTICAL_CENTER, OUTLINE_WIDTH_MM, OUTLINE_ROTATE)
frame = frames.build_frame(face)
single = frames.curve_rim(frame, 0)            # one rim, at the optical axis

export_stl(single, "right_eye_frame.stl")
bb = single.bounding_box()
print(f"wrote right_eye_frame.stl  ({bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm, "
      f"solids={len(single.solids())})")

if WITH_LENS:
    export_stl(frames.build_lens(face), "right_eye_lens.stl")
    print("wrote right_eye_lens.stl")
