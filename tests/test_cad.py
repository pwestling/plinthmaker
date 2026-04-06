import math
import unittest

import cadquery as cq
import src.cad as cad


class CadGeometryTests(unittest.TestCase):
    def bottom_hole_centers(self, obj: cq.Workplane) -> list[tuple[float, float, float]]:
        bottom_face = obj.faces("<Z").vals()[0]
        return [wire.Center().toTuple() for wire in bottom_face.innerWires()]

    def rounded_xy_centers(self, obj: cq.Workplane) -> list[tuple[float, float]]:
        return sorted(
            (round(x, 6), round(y, 6))
            for x, y, _ in self.bottom_hole_centers(obj)
        )

    def top_face_center(self, obj: cq.Workplane) -> tuple[float, float, float]:
        return obj.faces(">Z").val().Center().toTuple()

    def test_rectangle_plinth_base_extrudes_along_negative_y(self) -> None:
        obj = cad.rectangle_plinth_base(cq.Workplane("XZ"), 5, 7, 10, slope_angle=25)

        bounding_box = obj.val().BoundingBox()

        self.assertAlmostEqual(bounding_box.xmin, 0.0)
        self.assertAlmostEqual(bounding_box.xmax, 5.0)
        self.assertAlmostEqual(bounding_box.ymin, -10.0)
        self.assertAlmostEqual(bounding_box.ymax, 0.0)
        self.assertAlmostEqual(bounding_box.zmin, 0.0)
        self.assertAlmostEqual(bounding_box.zmax, 7.0)

    def test_add_center_pole_places_axis_at_requested_point(self) -> None:
        obj = cad.add_center_pole(cq.Workplane("XZ"), (2.5, 5.0), 10, 1)

        bounding_box = obj.val().BoundingBox()

        self.assertAlmostEqual(bounding_box.xmin, 2.0)
        self.assertAlmostEqual(bounding_box.xmax, 3.0)
        self.assertAlmostEqual(bounding_box.ymin, -5.5)
        self.assertAlmostEqual(bounding_box.ymax, -4.5)
        self.assertAlmostEqual(bounding_box.zmin, 0.0)
        self.assertAlmostEqual(bounding_box.zmax, 10.0)

    def test_add_bottom_holes_respects_configurable_inset_for_circles(self) -> None:
        obj = cad.circular_plinth_base(cq.Workplane("XY"), 20, 10)
        obj = cad.add_bottom_holes(obj, 4, 3, 4, inset=2)

        centers = self.bottom_hole_centers(obj)

        self.assertEqual(len(centers), 4)
        for x, y, z in centers:
            self.assertAlmostEqual(math.hypot(x, y), 16.0, places=6)
            self.assertAlmostEqual(z, 0.0)

    def test_circular_plinth_base_tilts_top_plane_about_x_axis(self) -> None:
        radius = 20
        height = 10
        slope_angle = 10
        obj = cad.circular_plinth_base(
            cq.Workplane("XY"),
            radius,
            height,
            slope_angle=slope_angle,
        )

        bounding_box = obj.val().BoundingBox()
        top_face = obj.faces(">Z").val()
        top_face_center = top_face.Center().toTuple()
        top_face_bounds = top_face.BoundingBox()
        top_height_offset = math.tan(math.radians(slope_angle)) * radius

        self.assertAlmostEqual(top_face_center[0], 0.0, places=6)
        self.assertAlmostEqual(top_face_center[1], 0.0, places=6)
        self.assertAlmostEqual(top_face_center[2], height, places=6)
        self.assertAlmostEqual(top_face_bounds.zmin, height - top_height_offset, places=6)
        self.assertAlmostEqual(top_face_bounds.zmax, height + top_height_offset, places=6)
        self.assertAlmostEqual(bounding_box.zmin, 0.0, places=6)
        self.assertAlmostEqual(bounding_box.zmax, height + top_height_offset, places=6)

    def test_add_bottom_holes_uses_inset_ellipse_for_rectangles(self) -> None:
        obj = cad.rectangle_plinth_base(cq.Workplane("XZ"), 40, 10, 20)
        obj = cad.add_bottom_holes(obj, 4, 3, 2)

        self.assertEqual(
            self.rounded_xy_centers(obj),
            [
                (6.0, -10.0),
                (20.0, -14.0),
                (20.0, -6.0),
                (34.0, -10.0),
            ],
        )

    def test_add_bottom_holes_start_angle_rotates_two_hole_ellipse_axis(self) -> None:
        obj = cad.rectangle_plinth_base(cq.Workplane("XZ"), 40, 10, 20)
        obj = cad.add_bottom_holes(obj, 2, 3, 2, start_angle=90)

        self.assertEqual(
            self.rounded_xy_centers(obj),
            [
                (20.0, -14.0),
                (20.0, -6.0),
            ],
        )

    def test_add_bottom_holes_falls_back_to_center_when_holes_overlap(self) -> None:
        obj = cad.circular_plinth_base(cq.Workplane("XY"), 10, 10)
        obj = cad.add_bottom_holes(obj, 8, 3, 6)

        centers = self.bottom_hole_centers(obj)

        self.assertEqual(len(centers), 1)
        self.assertAlmostEqual(centers[0][0], 0.0, places=6)
        self.assertAlmostEqual(centers[0][1], 0.0, places=6)
        self.assertAlmostEqual(centers[0][2], 0.0)

    def test_add_bottom_holes_uses_base_footprint_after_backdrop(self) -> None:
        obj = cad.rectangle_plinth_base(cq.Workplane("XZ"), 12, 7, 40)
        obj = cad.backdrop(obj, 10, 40, 10)
        obj = cad.add_bottom_holes(obj, 2, 3, 2)

        centers = self.bottom_hole_centers(obj)

        self.assertEqual(len(centers), 1)
        self.assertAlmostEqual(centers[0][0], 6.0, places=6)
        self.assertAlmostEqual(centers[0][1], -20.0, places=6)
        self.assertAlmostEqual(centers[0][2], 0.0)

    def test_make_circular_plinth_centers_optional_pole(self) -> None:
        slope_angle = 10
        obj = cad.make_circular_plinth(
            cad.CircularPlinthSpec(
                radius=20,
                height=10,
                slope_angle=slope_angle,
                center_pole=cad.CenterPoleConfig(height=12, diameter=4),
            )
        )

        top_face_center = self.top_face_center(obj)
        expected_top_z = 22.0

        self.assertAlmostEqual(top_face_center[0], 0.0, places=6)
        self.assertAlmostEqual(top_face_center[1], 0.0, places=6)
        self.assertAlmostEqual(top_face_center[2], expected_top_z, places=6)

    def test_make_circular_plinth_applies_optional_bottom_holes(self) -> None:
        obj = cad.make_circular_plinth(
            cad.CircularPlinthSpec(
                radius=20,
                height=10,
                bottom_holes=cad.BottomHolesConfig(
                    hole_count=4,
                    hole_depth=3,
                    hole_diameter=4,
                    inset=2,
                ),
            )
        )

        self.assertEqual(len(self.bottom_hole_centers(obj)), 4)

    def test_make_rectangular_plinth_infers_center_pole_and_full_width_backdrop(self) -> None:
        obj = cad.make_rectangular_plinth(
            cad.RectangularPlinthSpec(
                depth=40,
                width=20,
                height=10,
                center_pole=cad.CenterPoleConfig(height=15, diameter=4),
                backdrop=cad.BackdropConfig(height=12, depth=3),
            )
        )

        top_face_center = self.top_face_center(obj)
        backdrop_face_bounds = obj.faces(">X").val().BoundingBox()

        self.assertAlmostEqual(top_face_center[0], 20.0, places=6)
        self.assertAlmostEqual(top_face_center[1], -10.0, places=6)
        self.assertAlmostEqual(top_face_center[2], 25.0, places=6)
        self.assertAlmostEqual(backdrop_face_bounds.xmin, 43.0, places=6)
        self.assertAlmostEqual(backdrop_face_bounds.xmax, 43.0, places=6)
        self.assertAlmostEqual(backdrop_face_bounds.ymin, -20.0, places=6)
        self.assertAlmostEqual(backdrop_face_bounds.ymax, 0.0, places=6)
        self.assertAlmostEqual(backdrop_face_bounds.zmin, 0.0, places=6)
        self.assertAlmostEqual(backdrop_face_bounds.zmax, 22.0, places=6)

    def test_make_rectangular_plinth_interprets_center_pole_height_above_local_top(self) -> None:
        slope_angle = 10
        obj = cad.make_rectangular_plinth(
            cad.RectangularPlinthSpec(
                depth=40,
                width=20,
                height=10,
                slope_angle=slope_angle,
                center_pole=cad.CenterPoleConfig(height=5, diameter=4),
            )
        )

        top_face_center = self.top_face_center(obj)
        expected_top_z = 10 - math.tan(math.radians(slope_angle)) * 20 + 5

        self.assertAlmostEqual(top_face_center[0], 20.0, places=6)
        self.assertAlmostEqual(top_face_center[1], -10.0, places=6)
        self.assertAlmostEqual(top_face_center[2], expected_top_z, places=6)

    def test_make_rectangular_plinth_applies_optional_bottom_holes(self) -> None:
        obj = cad.make_rectangular_plinth(
            cad.RectangularPlinthSpec(
                depth=40,
                width=20,
                height=10,
                bottom_holes=cad.BottomHolesConfig(
                    hole_count=2,
                    hole_depth=3,
                    hole_diameter=2,
                    start_angle=90,
                ),
            )
        )

        self.assertEqual(
            self.rounded_xy_centers(obj),
            [
                (20.0, -14.0),
                (20.0, -6.0),
            ],
        )


if __name__ == "__main__":
    unittest.main()
