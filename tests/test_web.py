import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.minicompare import MiniCompareImage, MiniCompareMini


client = TestClient(app)


class FakeMiniCompareCatalog:
    async def search(self, query: str, *, limit: int = 16) -> list[MiniCompareMini]:
        return [
            MiniCompareMini(
                id="primaris-intercessor-a",
                name="Primaris Intercessor A",
                collection="Games Workshop › Warhammer 40k › Space Marines",
                image_url=(
                    "https://minicompare.info/assets/collection/games-workshop/"
                    "warhammer-40k/space-marines/primaris-intercessor-a.webp"
                ),
                search_text=query.lower(),
            )
        ][:limit]

    async def get_image(self, mini_id: str) -> MiniCompareImage:
        return MiniCompareImage(content=b"fake-webp", media_type="image/webp")


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
        self.assertIn('id="scale_reference_mini_id_hidden"', response.text)
        self.assertIn('id="scale_reference_mini_name_hidden"', response.text)
        self.assertIn('id="mini-search"', response.text)
        self.assertIn('id="mini-search-results"', response.text)
        self.assertIn("MiniCompare", response.text)
        self.assertIn('data-show-mini-reference="false"', response.text)
        self.assertNotIn('id="preview-scale-reference-toggle"', response.text)
        self.assertIn("Current draft", response.text)
        self.assertIn("Recent downloads", response.text)
        self.assertIn('aria-label="Configuration views"', response.text)
        self.assertIn("Configure", response.text)
        self.assertIn("History", response.text)
        self.assertIn("Configuration name", response.text)
        self.assertIn("configurationName", response.text)
        self.assertIn("Name this configuration", response.text)
        self.assertIn("renameHistoryEntry", response.text)
        self.assertIn("data-history-panel", response.text)
        self.assertIn("data-configuration-panel", response.text)
        self.assertIn("data-history-download", response.text)
        self.assertIn('name="center_feature"', response.text)
        self.assertIn('value="hole"', response.text)
        self.assertIn('id="center-hole-fields"', response.text)
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
                "center_feature": "hole",
                "center_hole_depth": "18",
                "center_hole_diameter": "4",
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
        self.assertIn("data-history-download", response.text)
        self.assertIn("plinth_type=circular", response.text)
        self.assertIn("center_feature=hole", response.text)
        self.assertIn("Center hole", response.text)
        self.assertIn("circular_diameter=44", response.text)
        self.assertIn("start angle", response.text)
        self.assertIn("Footer", response.text)
        self.assertIn("MiniCompare reference", response.text)
        self.assertIn("No mini selected", response.text)
        self.assertIn('data-show-mini-reference="false"', response.text)
        self.assertNotIn("preview-scale-reference-toggle", response.text)

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
        self.assertIn('data-show-mini-reference="false"', response.text)
        self.assertIn("No mini selected", response.text)

    def test_preview_renders_selected_minicompare_cutout_at_mount_height(self) -> None:
        response = client.post(
            "/preview",
            data={
                "plinth_type": "rectangular",
                "include_scale_reference": "true",
                "scale_reference_mini_id": "primaris-intercessor-a",
                "scale_reference_mini_name": "Primaris Intercessor A",
                "height": "60",
                "depth": "55",
                "width": "55",
                "slope_angle": "0",
                "center_feature": "pole",
                "center_pole_height": "20",
                "center_pole_diameter": "7.62",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-show-mini-reference="true"', response.text)
        self.assertIn('data-mini-id="primaris-intercessor-a"', response.text)
        self.assertIn('data-mini-name="Primaris Intercessor A"', response.text)
        self.assertIn(
            '/api/minicompare/image/primaris-intercessor-a',
            response.text,
        )
        self.assertIn('data-mount-height="80.0"', response.text)
        self.assertIn('id="preview-scale-reference-toggle"', response.text)
        self.assertIn("shown in preview only", response.text)
        self.assertNotIn("scale_reference_mini_id=", response.text)

    def test_preview_can_hide_selected_minicompare_cutout(self) -> None:
        response = client.post(
            "/preview",
            data={
                "plinth_type": "rectangular",
                "include_scale_reference": "false",
                "scale_reference_mini_id": "primaris-intercessor-a",
                "scale_reference_mini_name": "Primaris Intercessor A",
                "height": "60",
                "depth": "55",
                "width": "55",
                "slope_angle": "0",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-show-mini-reference="false"', response.text)
        self.assertIn("selected, hidden", response.text)
        self.assertIn('id="preview-scale-reference-toggle"', response.text)
        self.assertNotIn("checked", response.text)

    def test_preview_accepts_legacy_minicompare_id_characters(self) -> None:
        response = client.post(
            "/preview",
            data={
                "plinth_type": "rectangular",
                "include_scale_reference": "true",
                "scale_reference_mini_id": "bladeguard Veteran_wh+-a",
                "scale_reference_mini_name": "Bladeguard Veteran A",
                "height": "60",
                "depth": "55",
                "width": "55",
                "slope_angle": "0",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-show-mini-reference="true"', response.text)
        self.assertIn('data-mini-id="bladeguard Veteran_wh+-a"', response.text)

    def test_minicompare_search_returns_same_origin_image_urls(self) -> None:
        with patch("app.main.minicompare_catalog", FakeMiniCompareCatalog()):
            response = client.get("/api/minicompare/search", params={"q": "intercessor"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 1)
        item = response.json()["items"][0]
        self.assertEqual(item["id"], "primaris-intercessor-a")
        self.assertEqual(item["name"], "Primaris Intercessor A")
        self.assertEqual(
            item["image_url"],
            "http://testserver/api/minicompare/image/primaris-intercessor-a",
        )
        self.assertEqual(
            item["source_url"],
            "https://minicompare.info/?primaris-intercessor-a=",
        )

    def test_minicompare_image_proxy_preserves_image_type_and_adds_cache_headers(
        self,
    ) -> None:
        with patch("app.main.minicompare_catalog", FakeMiniCompareCatalog()):
            response = client.get(
                "/api/minicompare/image/primaris-intercessor-a"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"fake-webp")
        self.assertEqual(response.headers["content-type"], "image/webp")
        self.assertEqual(response.headers["cache-control"], "public, max-age=86400")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")

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
                "center_feature": "pole",
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
