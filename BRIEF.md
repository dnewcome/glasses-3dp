# glasses-3dp — kickoff brief

- **Problem:** Make 3D-printable (SLA) eyeglass frames that snap-retain real salvaged lenses, via a parametric model that differences a modeled lens out of a frame blank.
- **Done looks like:** A build123d script that takes a lens outline SVG + base-curve radius + edge params and outputs a printable single-eye frame rim with a correctly curved seat and V-groove that the lens snaps into.
- **Not now:** Bridge/nose pads (bridge is molded in solid later), temples beyond hinge *pockets*, true PD precision, real-lens measurement pipeline (use nominal dims first).
- **First slice:** Generic lens SVG → lens solid (front/back spheres + swept V-bevel) → boolean-difference into a rim band to produce the seated groove; export STL.
- **Open question:** Whether the swept V-bevel along the sphere-projected outline booleans cleanly in OCCT, and whether the rigid-groove snap actually seats given SLA resin stiffness.

## Reference notes
- **Base curve → radius:** lens clock reads diopters assuming n=1.53. Extract geometry with `R(mm) = 530 / D_read`, ignoring the (index-dependent, possibly wrong) diopter label.
- **Toolchain:** build123d (OCCT/OCP kernel), chosen over CadQuery for cleaner sweep/path handling, over OpenSCAD for clean curved B-rep + STL.
- **V-bevel:** apex angle ~110–120°, apex ridge ~1/3 from front face. Frame channel = "bezel"/"lens groove".
