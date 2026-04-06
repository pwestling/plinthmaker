import math
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import cadquery as cq
from pydantic import BaseModel, ConfigDict, Field


BOTTOM_HOLE_INSET = 5.0


@dataclass(frozen=True)
class PlinthBaseFootprint:
    center_x: float
    center_y: float
    bottom_z: float
    semi_axis_x: float
    semi_axis_y: float


class PlinthComponentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CenterPoleConfig(PlinthComponentConfig):
    """
    Dimensions for an optional vertical pole centered on a plinth footprint.

    In the packaged plinth builders, the pole axis is inferred from the plinth
    footprint center and `height` is interpreted as how far the pole extends
    above the local top surface at that centered location.
    """

    height: float = Field(
        gt=0,
        description=(
            "Additional height of the cylindrical pole above the local top surface "
            "at the centered pole axis. The packaged plinth builders add this "
            "value to the base top height at the pole location; the low-level "
            "add_center_pole() helper still takes an absolute height from z = 0."
        ),
    )
    diameter: float = Field(
        gt=0,
        description="Outside diameter of the cylindrical pole.",
    )


class BottomHolesConfig(PlinthComponentConfig):
    """
    Dimensions for optional magnet or heat-set insert holes in the bottom face.

    Each hole is a cylindrical cut that starts on the plinth bottom plane at
    `z = 0` and extends upward into the body of the plinth.
    """

    hole_count: int = Field(
        gt=0,
        description=(
            "Number of holes to attempt to place around the inset ellipse on the "
            "bottom face. If the requested pattern would overlap, the build falls "
            "back to one centered hole."
        ),
    )
    hole_depth: float = Field(
        gt=0,
        description=(
            "Depth of each cylindrical hole measured upward from the bottom plane "
            "at z = 0."
        ),
    )
    hole_diameter: float = Field(
        gt=0,
        description="Diameter of each cylindrical hole.",
    )
    inset: float = Field(
        default=BOTTOM_HOLE_INSET,
        ge=0,
        description=(
            "Offset from the base footprint to the hole-placement ellipse, measured "
            "from the outside edge of each hole. Larger values move the holes "
            "toward the footprint center."
        ),
    )
    start_angle: float = Field(
        default=0.0,
        description=(
            "Angular offset in degrees applied to the hole-placement ellipse. "
            "0 degrees places the first hole on the +X side of the footprint; "
            "90 degrees rotates a two-hole pattern onto the Y axis."
        ),
    )


class BackdropConfig(PlinthComponentConfig):
    """
    Dimensions for an optional wall attached to the +X side of a rectangular plinth.

    The backdrop always spans the full rectangular plinth width, so only its
    extension above the base top and its outward thickness are configurable.
    """

    height: float = Field(
        gt=0,
        description=(
            "Additional height of the backdrop wall above the rectangular plinth's "
            "top rear edge. The packaged rectangular builder adds this value to "
            "the base height, so a 12 mm backdrop on a 60 mm base reaches "
            "z = 72 mm at the back face."
        ),
    )
    depth: float = Field(
        gt=0,
        description=(
            "Thickness of the backdrop wall extruded outward from the plinth's +X "
            "face."
        ),
    )


class CircularPlinthSpec(PlinthComponentConfig):
    """
    Top-level configuration for a circular plinth centered on the world XY origin.

    The circular footprint is centered at `(0, 0)` in XY. The plinth bottom sits
    on `z = 0`, and the base extends upward from there.
    """

    radius: float = Field(
        gt=0,
        description=(
            "Radius of the circular footprint at the bottom face. The bottom edge "
            "lies in the XY plane and is centered on the world origin."
        ),
    )
    height: float = Field(
        gt=0,
        description=(
            "Height of the outer rim measured from the bottom plane at z = 0. "
            "With a positive slope angle, the top surface sits lower at the center "
            "than it does at the outer rim."
        ),
    )
    slope_angle: float = Field(
        default=0.0,
        description=(
            "Top-surface tilt in degrees from rotating the circular top plane about "
            "the world X axis while keeping the center fixed at `height`. "
            "0 degrees produces a flat top; positive values raise the +Y side "
            "of the rim and lower the -Y side."
        ),
    )
    center_pole: CenterPoleConfig | None = Field(
        default=None,
        description=(
            "Optional centered cylindrical pole. When provided, the pole axis is "
            "placed automatically at the center of the circular footprint, and "
            "its configured height is measured above the circular top surface at "
            "that center point."
        ),
    )
    bottom_holes: BottomHolesConfig | None = Field(
        default=None,
        description="Optional holes cut upward from the bottom face.",
    )


class RectangularPlinthSpec(PlinthComponentConfig):
    """
    Top-level configuration for a rectangular plinth aligned to the world axes.

    The rectangular bottom footprint spans X from `0` to `depth`, Y from
    `-width` to `0`, and Z from `0` upward. The footprint center therefore sits
    at `(depth / 2, -width / 2)` in world space.
    """

    depth: float = Field(
        gt=0,
        description=(
            "Front-to-back size of the rectangular footprint in millimeters. The "
            "base spans world X from 0 at the front edge to `depth` at the back "
            "edge."
        ),
    )
    width: float = Field(
        gt=0,
        description=(
            "Left-to-right size of the rectangular footprint in millimeters. The "
            "base spans world Y from `-width` to 0 because the side profile is "
            "extruded from the XZ workplane along negative world Y."
        ),
    )
    height: float = Field(
        gt=0,
        description=(
            "Height of the back edge measured upward from the bottom plane at "
            "z = 0. With a positive slope angle, the front edge is lower than "
            "this value."
        ),
    )
    slope_angle: float = Field(
        default=0.0,
        description=(
            "Top-surface slope in degrees along +X. 0 degrees produces a flat top; "
            "positive values make the top rise from the front edge toward the "
            "back edge."
        ),
    )
    center_pole: CenterPoleConfig | None = Field(
        default=None,
        description=(
            "Optional centered cylindrical pole. When provided, the pole axis is "
            "placed automatically at the center of the rectangular footprint, and "
            "its configured height is measured above the sloped top surface at "
            "that center point."
        ),
    )
    bottom_holes: BottomHolesConfig | None = Field(
        default=None,
        description="Optional holes cut upward from the bottom face.",
    )
    backdrop: BackdropConfig | None = Field(
        default=None,
        description=(
            "Optional backdrop wall attached to the plinth's +X face. The wall "
            "always spans the full plinth width. Its configured height is the "
            "amount the wall extends above the base top at the back edge, not "
            "the total wall height from z = 0."
        ),
    )


PlinthSpec = CircularPlinthSpec | RectangularPlinthSpec


def _set_plinth_base_footprint(
    obj: cq.Workplane,
    *,
    center_x: float,
    center_y: float,
    bottom_z: float,
    semi_axis_x: float,
    semi_axis_y: float,
) -> cq.Workplane:
    obj._plinth_base_footprint = PlinthBaseFootprint( # type: ignore
        center_x=center_x,
        center_y=center_y,
        bottom_z=bottom_z,
        semi_axis_x=semi_axis_x,
        semi_axis_y=semi_axis_y,
    )
    return obj


def _copy_plinth_base_footprint(
    source: cq.Workplane,
    target: cq.Workplane,
) -> cq.Workplane:
    if hasattr(source, "_plinth_base_footprint"):
        target._plinth_base_footprint = source._plinth_base_footprint # type: ignore
    return target


def _require_plinth_base_footprint(obj: cq.Workplane) -> PlinthBaseFootprint:
    if not hasattr(obj, "_plinth_base_footprint"):
        raise ValueError(
            "Bottom hole placement requires a plinth base created by "
            "rectangle_plinth_base() or circular_plinth_base()."
        )
    return obj._plinth_base_footprint # type: ignore


def _add_pole_at_world_xy(
    obj: cq.Workplane,
    *,
    center_x: float,
    center_y: float,
    bottom_z: float,
    height: float,
    diameter: float,
) -> cq.Workplane:
    radius = diameter / 2
    pole = (
        cq.Workplane("XY", origin=(center_x, center_y, bottom_z))
        .circle(radius)
        .extrude(height)
    )
    result = obj.add(pole)
    return _copy_plinth_base_footprint(obj, result)


def _add_centered_pole(
    obj: cq.Workplane,
    *,
    height: float,
    diameter: float,
) -> cq.Workplane:
    footprint = _require_plinth_base_footprint(obj)
    return _add_pole_at_world_xy(
        obj,
        center_x=footprint.center_x,
        center_y=footprint.center_y,
        bottom_z=footprint.bottom_z,
        height=height,
        diameter=diameter,
    )


def _rectangular_top_z_at_center(
    *,
    depth: float,
    height: float,
    slope_angle: float,
) -> float:
    return height - math.tan(math.radians(slope_angle)) * (depth / 2)


def _circular_top_z_at_center(
    *,
    height: float,
) -> float:
    return height


def rectangle_plinth_base(
    obj: cq.Workplane,
    depth: float,
    height: float,
    width: float,
    slope_angle: float = 0,
) -> cq.Workplane:
    """
    Create a rectangular plinth by extruding a side profile drawn on the XZ plane.

    CadQuery's XZ workplane uses -Y as its normal, so a positive `width` extends
    the base across world-space Y from `-width` to `0`.

    `slope_angle` is measured in degrees (0 = flat top).
    """

    top_left_z = height - math.tan(math.radians(slope_angle)) * depth

    side_profile = (
        cq.Workplane("XZ")
        .moveTo(0, 0)
        .lineTo(depth, 0)
        .lineTo(depth, height)
        .lineTo(0, top_left_z)
        .close()
        .extrude(width)
    )

    result = obj.add(side_profile)
    return _set_plinth_base_footprint(
        result,
        center_x=depth / 2,
        center_y=-width / 2,
        bottom_z=0.0,
        semi_axis_x=depth / 2,
        semi_axis_y=width / 2,
    )


def circular_plinth_base(
    obj: cq.Workplane,
    radius: float,
    height: float,
    slope_angle: float = 0,
) -> cq.Workplane:
    """
    Create a circular plinth with vertical sides and an optionally tilted top.

    The solid is centered on the origin in XY and spans Z from `0` upward. The
    top face is a circle cut by a plane rotated about the world X axis through
    the point `(0, 0, height)`, so the top center stays fixed at `z = height`.
    `slope_angle` is measured in degrees (0 = flat top).
    """

    top_height_offset = math.tan(math.radians(slope_angle)) * radius
    total_height = height + abs(top_height_offset)

    base_cylinder = (
        cq.Workplane("XY")
        .circle(radius)
        .extrude(total_height)
    )

    if slope_angle == 0:
        result = obj.add(base_cylinder)
    else:
        plane_span = radius * 4
        cutter_depth = total_height + radius * 4
        top_cutter = (
            cq.Workplane("XY")
            .transformed(offset=(0, 0, height), rotate=(slope_angle, 0, 0))
            .rect(plane_span, plane_span)
            .extrude(cutter_depth)
        )
        result = obj.add(base_cylinder.cut(top_cutter))

    return _set_plinth_base_footprint(
        result,
        center_x=0.0,
        center_y=0.0,
        bottom_z=0.0,
        semi_axis_x=radius,
        semi_axis_y=radius,
    )


def add_center_pole(
    obj: cq.Workplane,
    center: tuple[float, float] | tuple[float, float, float],
    height: float,
    diameter: float,
) -> cq.Workplane:
    """
    Add a vertical cylinder whose axis passes through `center` in world-space XY.

    For rectangular plinths, use positive Y distances measured from the front
    edge. `rectangle_plinth_base()` extrudes along -Y, so the pole is placed at
    `(x, -y, z)` in world coordinates.
    """

    if len(center) == 2:
        cx, cy = center
        z0 = 0.0
    else:
        cx, cy, z0 = center

    return _add_pole_at_world_xy(
        obj,
        center_x=cx,
        center_y=-cy,
        bottom_z=z0,
        height=height,
        diameter=diameter,
    )


def add_bottom_holes(
    obj: cq.Workplane,
    hole_count: int,
    hole_depth: float,
    hole_diameter: float,
    inset: float = BOTTOM_HOLE_INSET,
    start_angle: float = 0,
) -> cq.Workplane:
    """
    Cut magnet or heat-set insert holes into the bottom of the plinth base.

    The requested holes are placed evenly around an inset ellipse derived from
    the base footprint. `start_angle` is in degrees and rotates the placement
    pattern around the ellipse. If that would make the holes overlap, a single
    centered hole is cut instead.
    """

    if hole_count < 1:
        raise ValueError("hole_count must be at least 1")
    if hole_depth <= 0:
        raise ValueError("hole_depth must be positive")
    if hole_diameter <= 0:
        raise ValueError("hole_diameter must be positive")
    if inset < 0:
        raise ValueError("inset must be non-negative")

    footprint = _require_plinth_base_footprint(obj)
    hole_radius = hole_diameter / 2
    hole_positions = [(footprint.center_x, footprint.center_y)]
    start_angle_radians = math.radians(start_angle)

    if hole_count > 1:
        placement_semi_axis_x = footprint.semi_axis_x - inset - hole_radius
        placement_semi_axis_y = footprint.semi_axis_y - inset - hole_radius

        if placement_semi_axis_x > 0 and placement_semi_axis_y > 0:
            candidate_positions = [
                (
                    footprint.center_x
                    + placement_semi_axis_x
                    * math.cos(
                        start_angle_radians + 2 * math.pi * index / hole_count
                    ),
                    footprint.center_y
                    + placement_semi_axis_y
                    * math.sin(
                        start_angle_radians + 2 * math.pi * index / hole_count
                    ),
                )
                for index in range(hole_count)
            ]
            minimum_spacing = min(
                math.hypot(x1 - x2, y1 - y2)
                for i, (x1, y1) in enumerate(candidate_positions)
                for x2, y2 in candidate_positions[i + 1 :]
            )

            if minimum_spacing >= hole_diameter:
                hole_positions = candidate_positions

    holes = (
        cq.Workplane("XY", origin=(0, 0, footprint.bottom_z))
        .pushPoints(hole_positions)
        .circle(hole_radius)
        .extrude(hole_depth)
    )
    result = obj.cut(holes)
    return _copy_plinth_base_footprint(obj, result)


def backdrop(
    obj: cq.Workplane,
    height: float,
    width: float,
    depth: float,
) -> cq.Workplane:
    """
    Add a vertical wall to the plinth's +X face.

    The backdrop sketch is drawn in the selected face's local coordinates, so
    `width` maps across world-space Y and `depth` extrudes outward in +X.
    `height` is the wall's total height from the bottom plane at z = 0.
    """

    wall = (
        obj.faces(">X")
        .workplane()
        .moveTo(0, 0)
        .lineTo(-width, 0)
        .lineTo(-width, height)
        .lineTo(0, height)
        .close()
        .extrude(depth)
    )
    result = obj.add(wall)
    return _copy_plinth_base_footprint(obj, result)


def make_circular_plinth(spec: CircularPlinthSpec) -> cq.Workplane:
    """
    Build a circular plinth from a validated top-level specification.

    Optional features are inferred from the base geometry: the pole is centered
    on the circular footprint, and bottom holes are placed relative to the
    circular base footprint.
    """

    obj = cq.Workplane("XY")
    obj = circular_plinth_base(
        obj,
        radius=spec.radius,
        height=spec.height,
        slope_angle=spec.slope_angle,
    )

    if spec.center_pole is not None:
        pole_total_height = _circular_top_z_at_center(
            height=spec.height,
        ) + spec.center_pole.height
        obj = _add_centered_pole(
            obj,
            height=pole_total_height,
            diameter=spec.center_pole.diameter,
        )

    if spec.bottom_holes is not None:
        obj = add_bottom_holes(
            obj,
            hole_count=spec.bottom_holes.hole_count,
            hole_depth=spec.bottom_holes.hole_depth,
            hole_diameter=spec.bottom_holes.hole_diameter,
            inset=spec.bottom_holes.inset,
            start_angle=spec.bottom_holes.start_angle,
        )

    return obj


def make_rectangular_plinth(spec: RectangularPlinthSpec) -> cq.Workplane:
    """
    Build a rectangular plinth from a validated top-level specification.

    Optional features are inferred from the base geometry: the pole is centered
    on the rectangular footprint, the backdrop spans the full base width, and
    bottom holes are placed relative to the original base footprint.
    """

    obj = cq.Workplane("XZ")
    obj = rectangle_plinth_base(
        obj,
        depth=spec.depth,
        height=spec.height,
        width=spec.width,
        slope_angle=spec.slope_angle,
    )

    if spec.center_pole is not None:
        pole_total_height = _rectangular_top_z_at_center(
            depth=spec.depth,
            height=spec.height,
            slope_angle=spec.slope_angle,
        ) + spec.center_pole.height
        obj = _add_centered_pole(
            obj,
            height=pole_total_height,
            diameter=spec.center_pole.diameter,
        )

    if spec.backdrop is not None:
        obj = backdrop(
            obj,
            height=spec.height + spec.backdrop.height,
            width=spec.width,
            depth=spec.backdrop.depth,
        )

    if spec.bottom_holes is not None:
        obj = add_bottom_holes(
            obj,
            hole_count=spec.bottom_holes.hole_count,
            hole_depth=spec.bottom_holes.hole_depth,
            hole_diameter=spec.bottom_holes.hole_diameter,
            inset=spec.bottom_holes.inset,
            start_angle=spec.bottom_holes.start_angle,
        )

    return obj


def build_plinth(spec: PlinthSpec) -> cq.Workplane:
    if isinstance(spec, CircularPlinthSpec):
        return make_circular_plinth(spec)

    return make_rectangular_plinth(spec)


def export_stl_bytes(model: cq.Workplane, filename: str = "plinth.stl") -> bytes:
    with TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / filename
        cq.exporters.export(model, str(output_path))
        return output_path.read_bytes()


def build_demo_plinth() -> cq.Workplane:
    return make_rectangular_plinth(
        RectangularPlinthSpec(
            depth=50,
            height=70,
            width=100,
            slope_angle=25,
            center_pole=CenterPoleConfig(height=80, diameter=10),
            backdrop=BackdropConfig(height=100, depth=10),
            bottom_holes=BottomHolesConfig(
                hole_count=2,
                hole_depth=3,
                hole_diameter=2,
                start_angle=90,
            ),
        )
    )


def export_demo_plinth(path: Path = Path(__file__).with_name("plinth.stl")) -> Path:
    build_demo_plinth().export(str(path))
    return path


if __name__ == "__main__":
    export_demo_plinth()

obj = build_demo_plinth()
