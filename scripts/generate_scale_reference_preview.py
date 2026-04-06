from __future__ import annotations

from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_STL = REPO_ROOT / "SK_M01_01_02.stl"
OUTPUT_STL = REPO_ROOT / "static" / "SK_M01_01_02_preview.stl"
GRID_SIZE_MM = 0.13


def simplify_binary_stl(source_path: Path, output_path: Path, grid_size_mm: float) -> None:
    raw = source_path.read_bytes()
    triangle_count = int.from_bytes(raw[80:84], "little")
    triangle_dtype = np.dtype(
        [
            ("normal", "<f4", (3,)),
            ("verts", "<f4", (3, 3)),
            ("attr", "<u2"),
        ]
    )
    triangles = np.frombuffer(
        raw,
        dtype=triangle_dtype,
        offset=84,
        count=triangle_count,
    )

    mins = triangles["verts"].reshape(-1, 3).min(axis=0)
    snapped_vertices = (
        np.round((triangles["verts"] - mins) / grid_size_mm) * grid_size_mm + mins
    )

    degenerate_mask = (
        np.isclose(snapped_vertices[:, 0], snapped_vertices[:, 1]).all(axis=1)
        | np.isclose(snapped_vertices[:, 1], snapped_vertices[:, 2]).all(axis=1)
        | np.isclose(snapped_vertices[:, 0], snapped_vertices[:, 2]).all(axis=1)
    )
    kept_vertices = snapped_vertices[~degenerate_mask]

    canonical_vertices = np.sort(kept_vertices, axis=1)
    _, unique_indexes = np.unique(
        np.round(canonical_vertices, 5).reshape(-1, 9),
        axis=0,
        return_index=True,
    )
    kept_vertices = kept_vertices[np.sort(unique_indexes)]

    normals = np.cross(
        kept_vertices[:, 1] - kept_vertices[:, 0],
        kept_vertices[:, 2] - kept_vertices[:, 0],
    )
    normal_lengths = np.linalg.norm(normals, axis=1)
    valid_normal_mask = normal_lengths > 1e-9
    kept_vertices = kept_vertices[valid_normal_mask]
    normals = normals[valid_normal_mask] / normal_lengths[valid_normal_mask][:, None]

    simplified = np.zeros(len(kept_vertices), dtype=triangle_dtype)
    simplified["normal"] = normals.astype("<f4")
    simplified["verts"] = kept_vertices.astype("<f4")
    simplified["attr"] = 0

    header = b"Plinthmaker scale preview STL".ljust(80, b" ")
    output_path.write_bytes(
        header + np.uint32(len(simplified)).tobytes() + simplified.tobytes()
    )


if __name__ == "__main__":
    simplify_binary_stl(SOURCE_STL, OUTPUT_STL, GRID_SIZE_MM)
    print(f"Wrote {OUTPUT_STL.relative_to(REPO_ROOT)}")
