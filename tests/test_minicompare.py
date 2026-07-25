import asyncio
import unittest
from time import monotonic

from app.minicompare import MiniCompareCatalog, parse_catalog, validate_image_url


class MiniCompareCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog_data = {
            "_scalers": {
                "sir-scalesby": {
                    "32mm": {
                        "sir-scalesby-32mm": (
                            "https://minicompare.info/assets/collection/_scalers/"
                            "sir-scalesby/32mm/sir-scalesby-32mm.webp"
                        )
                    }
                }
            },
            "games-workshop": {
                "warhammer-40k": {
                    "space-marines": {
                        "primaris-intercessor": {
                            "primaris-intercessor-a": (
                                "https://minicompare.info/assets/collection/"
                                "games-workshop/warhammer-40k/space-marines/"
                                "primaris-intercessor/primaris-intercessor-a.webp"
                            )
                        },
                        "terminator": {
                            "deathwing-terminator-a": (
                                "https://minicompare.info/assets/collection/"
                                "games-workshop/warhammer-40k/space-marines/"
                                "terminator/deathwing-terminator-a.webp"
                            )
                        },
                    }
                }
            },
        }

    def test_parse_catalog_flattens_minis_and_excludes_scalers(self) -> None:
        minis = parse_catalog(self.catalog_data)

        self.assertEqual(
            [mini.id for mini in minis],
            ["deathwing-terminator-a", "primaris-intercessor-a"],
        )
        intercessor = minis[1]
        self.assertEqual(intercessor.name, "Primaris Intercessor A")
        self.assertEqual(
            intercessor.collection,
            (
                "Games Workshop › Warhammer 40K › Space Marines › "
                "Primaris Intercessor"
            ),
        )

    def test_search_matches_terms_across_name_and_collection(self) -> None:
        minis = parse_catalog(self.catalog_data)
        catalog = MiniCompareCatalog()
        catalog._items = minis
        catalog._items_by_id = {mini.id: mini for mini in minis}
        catalog._loaded_at = monotonic()

        results = asyncio.run(catalog.search("space marine intercessor"))

        self.assertEqual([mini.id for mini in results], ["primaris-intercessor-a"])

    def test_validate_image_url_only_accepts_minicompare_collection_assets(self) -> None:
        self.assertTrue(
            validate_image_url(
                "https://minicompare.info/assets/collection/vendor/game/mini.webp"
            )
        )
        self.assertFalse(
            validate_image_url(
                "https://example.com/assets/collection/vendor/game/mini.webp"
            )
        )
        self.assertFalse(
            validate_image_url(
                "https://minicompare.info/assets/collection/vendor/game/mini.svg"
            )
        )
        self.assertFalse(
            validate_image_url(
                "https://minicompare.info/assets/collection/vendor/game/mini.webp?x=1"
            )
        )


if __name__ == "__main__":
    unittest.main()
