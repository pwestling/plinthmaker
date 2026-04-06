from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_index_uses_semantic_shell_with_minimal_stylesheet() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "<aside" in response.text
    assert '<section id="preview-panel"' in response.text
    assert 'hx-post="/preview"' in response.text
    assert "<style" not in response.text
    assert 'rel="stylesheet"' in response.text
    assert '/static/styles.css' in response.text


def test_preview_renders_circular_partial_with_download_link() -> None:
    response = client.post(
        "/preview",
        data={
            "plinth_type": "circular",
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
        },
    )

    assert response.status_code == 200
    assert "<html" not in response.text
    assert "Circular plinth preview" in response.text
    assert "Download STL" in response.text
    assert "plinth_type=circular" in response.text
    assert "circular_diameter=44" in response.text
    assert "start angle" in response.text


def test_download_stl_returns_binary_model() -> None:
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
            "include_backdrop": "true",
            "backdrop_height": "12",
            "backdrop_depth": "3",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "model/stl"
    assert "attachment;" in response.headers["content-disposition"]
    assert "rectangular-plinth" in response.headers["content-disposition"]
    assert response.content
