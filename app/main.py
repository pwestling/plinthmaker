from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from src.cad import (
    BOTTOM_HOLE_INSET,
    BackdropConfig,
    BottomHolesConfig,
    CenterPoleConfig,
    CircularPlinthSpec,
    FooterConfig,
    PlinthSpec,
    RectangularPlinthSpec,
    build_plinth,
    export_stl_bytes,
)

BASE_DIR = Path(__file__).resolve().parent.parent
SCALE_REFERENCE_PREVIEW_PATH = BASE_DIR / "static" / "SK_M01_01_02_preview.stl"
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
PlinthType = Literal["circular", "rectangular"]

app = FastAPI(
    title="Plinth Builder",
    description="Configure a circular or rectangular plinth and download the STL.",
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

DisplayUnit = Literal["mm", "in"]

DEFAULT_FORM_VALUES: dict[str, object] = {
    "plinth_type": "rectangular",
    "display_units": "mm",
    "include_scale_reference": True,
    "circular_diameter": 110.0,
    "depth": 55.0,
    "width": 55.0,
    "height": 60.0,
    "slope_angle": 0.0,
    "include_center_pole": False,
    "center_pole_height": 20.0,
    "center_pole_diameter": 7.62,
    "include_bottom_holes": True,
    "bottom_hole_count": 2,
    "bottom_hole_depth": 3.0,
    "bottom_hole_diameter": 2.0,
    "bottom_hole_inset": BOTTOM_HOLE_INSET,
    "bottom_hole_start_angle": 90.0,
    "include_footer": False,
    "footer_height": 8.0,
    "footer_lower_outset": 4.0,
    "footer_upper_outset": 2.0,
    "footer_lower_band_height": 3.0,
    "footer_fillet_radius": 0.0,
    "include_backdrop": False,
    "backdrop_height": 12.0,
    "backdrop_depth": 3.0,
}


def format_dimension(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def format_angle(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def format_length(value_mm: float, display_units: DisplayUnit) -> str:
    if display_units == "in":
        return f"{value_mm / 25.4:.3f}".rstrip("0").rstrip(".")
    return format_dimension(value_mm)


def query_value(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return format_dimension(value)
    return str(value)


def validation_message(error: ValidationError | ValueError) -> str:
    if isinstance(error, ValidationError):
        return " ".join(entry["msg"] for entry in error.errors())
    return str(error)


def build_spec(
    *,
    plinth_type: PlinthType,
    display_units: DisplayUnit = "mm",
    include_scale_reference: bool = False,
    circular_diameter: float,
    depth: float,
    width: float,
    height: float,
    slope_angle: float,
    include_center_pole: bool,
    center_pole_height: float,
    center_pole_diameter: float,
    include_bottom_holes: bool,
    bottom_hole_count: int,
    bottom_hole_depth: float,
    bottom_hole_diameter: float,
    bottom_hole_inset: float,
    bottom_hole_start_angle: float,
    include_footer: bool,
    footer_height: float,
    footer_lower_outset: float,
    footer_upper_outset: float,
    footer_lower_band_height: float,
    footer_fillet_radius: float,
    include_backdrop: bool,
    backdrop_height: float,
    backdrop_depth: float,
) -> PlinthSpec:
    center_pole = None
    if include_center_pole:
        center_pole = CenterPoleConfig(
            height=center_pole_height,
            diameter=center_pole_diameter,
        )

    bottom_holes = None
    if include_bottom_holes:
        bottom_holes = BottomHolesConfig(
            hole_count=bottom_hole_count,
            hole_depth=bottom_hole_depth,
            hole_diameter=bottom_hole_diameter,
            inset=bottom_hole_inset,
            start_angle=bottom_hole_start_angle,
        )

    footer = None
    if include_footer:
        footer = FooterConfig(
            height=footer_height,
            lower_outset=footer_lower_outset,
            upper_outset=footer_upper_outset,
            lower_band_height=footer_lower_band_height,
            fillet_radius=footer_fillet_radius,
        )

    if plinth_type == "circular":
        return CircularPlinthSpec(
            radius=circular_diameter / 2,
            height=height,
            slope_angle=slope_angle,
            center_pole=center_pole,
            bottom_holes=bottom_holes,
            footer=footer,
        )

    backdrop = None
    if include_backdrop:
        backdrop = BackdropConfig(
            height=backdrop_height,
            depth=backdrop_depth,
        )

    return RectangularPlinthSpec(
        depth=depth,
        width=width,
        height=height,
        slope_angle=slope_angle,
        center_pole=center_pole,
        bottom_holes=bottom_holes,
        footer=footer,
        backdrop=backdrop,
    )


def filename_for_spec(spec: PlinthSpec) -> str:
    if isinstance(spec, CircularPlinthSpec):
        stem = (
            "circular-plinth-"
            f"radius-{spec.radius:.2f}-"
            f"height-{spec.height:.2f}-"
            f"slope-{spec.slope_angle:.1f}"
        )
    else:
        stem = (
            "rectangular-plinth-"
            f"depth-{spec.depth:.2f}-"
            f"width-{spec.width:.2f}-"
            f"height-{spec.height:.2f}-"
            f"slope-{spec.slope_angle:.1f}"
        )

    return f"{stem.replace('.', '_')}.stl"


def summary_items(spec: PlinthSpec, *, display_units: DisplayUnit) -> list[tuple[str, str]]:
    unit_label = "in" if display_units == "in" else "mm"
    items = [("Shape", "Circular" if isinstance(spec, CircularPlinthSpec) else "Rectangular")]

    if isinstance(spec, CircularPlinthSpec):
        items.extend(
            [
                ("Diameter", f"{format_length(spec.radius * 2, display_units)} {unit_label}"),
                ("Height", f"{format_length(spec.height, display_units)} {unit_label}"),
            ]
        )
    else:
        items.extend(
            [
                ("Depth", f"{format_length(spec.depth, display_units)} {unit_label}"),
                ("Width", f"{format_length(spec.width, display_units)} {unit_label}"),
                ("Height", f"{format_length(spec.height, display_units)} {unit_label}"),
            ]
        )

    items.append(("Slope angle", f"{format_angle(spec.slope_angle)}°"))

    if spec.footer is None:
        items.append(("Footer", "Not included"))
    else:
        lower_band_height = spec.footer.lower_band_height
        if lower_band_height is None:
            lower_band_height = spec.footer.height * 0.4
        items.append(
            (
                "Footer",
                (
                    f"{format_length(spec.footer.height, display_units)} {unit_label} tall, "
                    f"{format_length(spec.footer.lower_outset, display_units)} {unit_label} lower outset, "
                    f"{format_length(spec.footer.upper_outset, display_units)} {unit_label} upper outset, "
                    f"{format_length(lower_band_height, display_units)} {unit_label} lower band, "
                    f"{format_length(spec.footer.fillet_radius, display_units)} {unit_label} fillet"
                ),
            )
        )

    if spec.center_pole is None:
        items.append(("Center pole", "Not included"))
    else:
        items.append(
            (
                "Center pole",
                (
                    f"{format_length(spec.center_pole.height, display_units)} {unit_label} above base top, "
                    f"{format_length(spec.center_pole.diameter, display_units)} {unit_label} diameter"
                ),
            )
        )

    if spec.bottom_holes is None:
        items.append(("Bottom holes", "Not included"))
    else:
        items.append(
            (
                "Bottom holes",
                (
                    f"{spec.bottom_holes.hole_count} requested, "
                    f"{format_length(spec.bottom_holes.hole_depth, display_units)} {unit_label} deep, "
                    f"{format_length(spec.bottom_holes.hole_diameter, display_units)} {unit_label} diameter, "
                    f"{format_length(spec.bottom_holes.inset, display_units)} {unit_label} inset, "
                    f"{format_angle(spec.bottom_holes.start_angle)}° start angle"
                ),
            )
        )

    if isinstance(spec, RectangularPlinthSpec):
        if spec.backdrop is None:
            items.append(("Backdrop", "Not included"))
        else:
            items.append(
                (
                    "Backdrop",
                    (
                        f"{format_length(spec.backdrop.height, display_units)} {unit_label} above base, "
                        f"{format_length(spec.width, display_units)} {unit_label} wide, "
                        f"{format_length(spec.backdrop.depth, display_units)} {unit_label} deep"
                    ),
                )
            )

    return items


def build_preview_context(
    request: Request,
    *,
    spec: PlinthSpec,
    form_values: dict[str, object],
) -> dict[str, object]:
    display_units = "mm"
    display_units_value = form_values.get("display_units")
    if display_units_value == "in":
        display_units = "in"
    include_scale_reference = bool(form_values.get("include_scale_reference"))
    stl_query_values = {
        key: value
        for key, value in form_values.items()
        if key not in {"display_units", "include_scale_reference"}
    }
    preview_summary_items = summary_items(spec, display_units=display_units)
    preview_summary_items.append(
        (
            "Scale reference",
            "Shown in preview only" if include_scale_reference else "Not shown",
        )
    )
    query_string = urlencode(
        {key: query_value(value) for key, value in stl_query_values.items()},
    )
    stl_path = str(app.url_path_for("download_stl"))
    return {
        "id": uuid4().hex,
        "title": "Circular plinth preview"
        if isinstance(spec, CircularPlinthSpec)
        else "Rectangular plinth preview",
        "spec": spec,
        "summary_items": preview_summary_items,
        "stl_url": f"{stl_path}?{query_string}",
        "include_scale_reference": include_scale_reference,
        "scale_reference_url": str(request.url_for("scale_reference_preview")),
        "filename": filename_for_spec(spec),
        "request": request,
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    spec = build_spec(**DEFAULT_FORM_VALUES)
    preview = build_preview_context(
        request,
        spec=spec,
        form_values=DEFAULT_FORM_VALUES,
    )
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "form": DEFAULT_FORM_VALUES,
            "preview": preview,
        },
    )


@app.get("/api/health", response_class=JSONResponse)
async def healthcheck() -> JSONResponse:
    return JSONResponse({"ok": True})


@app.get(
    "/preview-assets/SK_M01_01_02_preview-v1.stl",
    response_class=FileResponse,
    name="scale_reference_preview",
)
async def scale_reference_preview() -> FileResponse:
    return FileResponse(
        SCALE_REFERENCE_PREVIEW_PATH,
        media_type="model/stl",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
        },
    )


@app.post("/preview", response_class=HTMLResponse)
async def render_preview(
    request: Request,
    plinth_type: PlinthType = Form("rectangular"),
    display_units: DisplayUnit = Form("mm"),
    include_scale_reference: bool = Form(True),
    circular_diameter: float = Form(110.0),
    depth: float = Form(55.0),
    width: float = Form(55.0),
    height: float = Form(60.0),
    slope_angle: float = Form(0.0),
    include_center_pole: bool = Form(False),
    center_pole_height: float = Form(20.0),
    center_pole_diameter: float = Form(7.62),
    include_bottom_holes: bool = Form(False),
    bottom_hole_count: int = Form(2),
    bottom_hole_depth: float = Form(3.0),
    bottom_hole_diameter: float = Form(2.0),
    bottom_hole_inset: float = Form(BOTTOM_HOLE_INSET),
    bottom_hole_start_angle: float = Form(0.0),
    include_footer: bool = Form(False),
    footer_height: float = Form(8.0),
    footer_lower_outset: float = Form(4.0),
    footer_upper_outset: float = Form(2.0),
    footer_lower_band_height: float = Form(3.0),
    footer_fillet_radius: float = Form(0.0),
    include_backdrop: bool = Form(False),
    backdrop_height: float = Form(12.0),
    backdrop_depth: float = Form(3.0),
) -> HTMLResponse:
    form_values = {
        "plinth_type": plinth_type,
        "display_units": display_units,
        "include_scale_reference": include_scale_reference,
        "circular_diameter": circular_diameter,
        "depth": depth,
        "width": width,
        "height": height,
        "slope_angle": slope_angle,
        "include_center_pole": include_center_pole,
        "center_pole_height": center_pole_height,
        "center_pole_diameter": center_pole_diameter,
        "include_bottom_holes": include_bottom_holes,
        "bottom_hole_count": bottom_hole_count,
        "bottom_hole_depth": bottom_hole_depth,
        "bottom_hole_diameter": bottom_hole_diameter,
        "bottom_hole_inset": bottom_hole_inset,
        "bottom_hole_start_angle": bottom_hole_start_angle,
        "include_footer": include_footer,
        "footer_height": footer_height,
        "footer_lower_outset": footer_lower_outset,
        "footer_upper_outset": footer_upper_outset,
        "footer_lower_band_height": footer_lower_band_height,
        "footer_fillet_radius": footer_fillet_radius,
        "include_backdrop": include_backdrop,
        "backdrop_height": backdrop_height,
        "backdrop_depth": backdrop_depth,
    }
    try:
        spec = build_spec(**form_values)
    except (ValidationError, ValueError) as error:
        return templates.TemplateResponse(
            request=request,
            name="_error.html",
            context={
                "request": request,
                "message": validation_message(error),
            },
            status_code=422,
        )

    return templates.TemplateResponse(
        request=request,
        name="_preview.html",
        context={
            "request": request,
            "preview": build_preview_context(
                request,
                spec=spec,
                form_values=form_values,
            ),
        },
    )


@app.get("/api/model.stl", response_class=Response, name="download_stl")
async def download_stl(
    plinth_type: PlinthType = Query("rectangular"),
    circular_diameter: float = Query(110.0),
    depth: float = Query(55.0),
    width: float = Query(55.0),
    height: float = Query(60.0),
    slope_angle: float = Query(0.0),
    include_center_pole: bool = Query(False),
    center_pole_height: float = Query(20.0),
    center_pole_diameter: float = Query(7.62),
    include_bottom_holes: bool = Query(False),
    bottom_hole_count: int = Query(2),
    bottom_hole_depth: float = Query(3.0),
    bottom_hole_diameter: float = Query(2.0),
    bottom_hole_inset: float = Query(BOTTOM_HOLE_INSET),
    bottom_hole_start_angle: float = Query(0.0),
    include_footer: bool = Query(False),
    footer_height: float = Query(8.0),
    footer_lower_outset: float = Query(4.0),
    footer_upper_outset: float = Query(2.0),
    footer_lower_band_height: float = Query(3.0),
    footer_fillet_radius: float = Query(0.0),
    include_backdrop: bool = Query(False),
    backdrop_height: float = Query(12.0),
    backdrop_depth: float = Query(3.0),
) -> Response:
    try:
        spec = build_spec(
            plinth_type=plinth_type,
            circular_diameter=circular_diameter,
            depth=depth,
            width=width,
            height=height,
            slope_angle=slope_angle,
            include_center_pole=include_center_pole,
            center_pole_height=center_pole_height,
            center_pole_diameter=center_pole_diameter,
            include_bottom_holes=include_bottom_holes,
            bottom_hole_count=bottom_hole_count,
            bottom_hole_depth=bottom_hole_depth,
            bottom_hole_diameter=bottom_hole_diameter,
            bottom_hole_inset=bottom_hole_inset,
            bottom_hole_start_angle=bottom_hole_start_angle,
            include_footer=include_footer,
            footer_height=footer_height,
            footer_lower_outset=footer_lower_outset,
            footer_upper_outset=footer_upper_outset,
            footer_lower_band_height=footer_lower_band_height,
            footer_fillet_radius=footer_fillet_radius,
            include_backdrop=include_backdrop,
            backdrop_height=backdrop_height,
            backdrop_depth=backdrop_depth,
        )
    except (ValidationError, ValueError) as error:
        raise HTTPException(status_code=422, detail=validation_message(error)) from error

    try:
        filename = filename_for_spec(spec)
        stl_bytes = export_stl_bytes(build_plinth(spec), filename=filename)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"STL export failed: {error}") from error

    return Response(
        content=stl_bytes,
        media_type="model/stl",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
