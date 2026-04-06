import unittest

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


class WebAppTests(unittest.TestCase):
    def test_index_uses_semantic_shell_with_minimal_stylesheet(self) -> None:
        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("<aside", response.text)
        self.assertIn('<section id="preview-panel"', response.text)
        self.assertIn('hx-post="/preview"', response.text)
        self.assertNotIn("<style", response.text)
        self.assertIn('rel="stylesheet"', response.text)
        self.assertIn('/static/styles.css', response.text)
        self.assertIn('id="include_scale_reference_hidden"', response.text)
        self.assertIn('id="preview-scale-reference-toggle"', response.text)
        self.assertIn('value="true"', response.text)

    def test_preview_renders_circular_partial_with_download_link(self) -> None:
        response = client.post(
            "/preview",
            data={
                "plinth_type": "circular",
                "include_scale_reference": "true",
                "circular_diameter": "44",
                "depth": "40",
                "width": "20",
                "height": "14",
                "slope_angle": "8",
                "include_center_pole": "true",
                "center_pole_height": "18",
                "center_pole_diameter": "4",
                "include_bottom_holes": "true",
                "bottom_hole_count": "3",
                "bottom_hole_depth": "3",
                "bottom_hole_diameter": "4",
                "bottom_hole_inset": "5",
                "bottom_hole_start_angle": "30",
                "include_footer": "true",
                "footer_height": "8",
                "footer_lower_outset": "4",
                "footer_upper_outset": "2",
                "footer_lower_band_height": "3",
                "footer_fillet_radius": "0.5",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("<html", response.text)
        self.assertIn("Circular plinth preview", response.text)
        self.assertIn("Download STL", response.text)
        self.assertIn("plinth_type=circular", response.text)
        self.assertIn("circular_diameter=44", response.text)
        self.assertIn("start angle", response.text)
        self.assertIn("Footer", response.text)
        self.assertIn("Scale reference", response.text)
        self.assertIn("Shown in preview only", response.text)
        self.assertIn('data-show-scale-reference="true"', response.text)
        self.assertIn("SK_M01_01_02_preview-v1.stl", response.text)
        self.assertIn("preview-scale-reference-toggle", response.text)

    def test_preview_respects_scale_reference_false(self) -> None:
        response = client.post(
            "/preview",
            data={
                "plinth_type": "rectangular",
                "include_scale_reference": "false",
                "height": "60",
                "depth": "55",
                "width": "55",
                "slope_angle": "0",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-show-scale-reference="false"', response.text)
        self.assertIn("Not shown", response.text)

    def test_scale_reference_preview_asset_is_served_with_long_lived_cache_headers(self) -> None:
        response = client.get("/preview-assets/SK_M01_01_02_preview-v1.stl")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "model/stl")
        self.assertEqual(
            response.headers["cache-control"],
            "public, max-age=31536000, immutable",
        )
        self.assertIn("etag", response.headers)
        self.assertIn("last-modified", response.headers)
        self.assertTrue(response.content)

    def test_download_stl_returns_binary_model(self) -> None:
        response = client.get(
            "/api/model.stl",
            params={
                "plinth_type": "rectangular",
                "depth": "40",
                "width": "20",
                "height": "10",
                "slope_angle": "10",
                "include_center_pole": "true",
                "center_pole_height": "15",
                "center_pole_diameter": "4",
                "include_bottom_holes": "true",
                "bottom_hole_count": "2",
                "bottom_hole_depth": "3",
                "bottom_hole_diameter": "2",
                "bottom_hole_inset": "5",
                "bottom_hole_start_angle": "90",
                "include_footer": "true",
                "footer_height": "8",
                "footer_lower_outset": "4",
                "footer_upper_outset": "2",
                "footer_lower_band_height": "3",
                "footer_fillet_radius": "0.5",
                "include_backdrop": "true",
                "backdrop_height": "12",
                "backdrop_depth": "3",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "model/stl")
        self.assertIn("attachment;", response.headers["content-disposition"])
        self.assertIn("rectangular-plinth", response.headers["content-disposition"])
        self.assertTrue(response.content)


if __name__ == "__main__":
    unittest.main()
