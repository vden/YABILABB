"""FastAPI web application for YABILABB."""

import os
import uuid
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from yabilabb.cli import MODELOS
from yabilabb.models import Declaration, Declarant, Operator
from yabilabb.writer import write_349, _make_filename
from yabilabb.parser import parse_349
from yabilabb.yaml_io import save_declaration, load_declaration

app = FastAPI(title="YABILABB")

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
DATA_DIR = Path(os.environ.get("YABILABB_DATA_DIR", Path.home() / ".yabilabb")) / "declarations"


def _data_dir_for_modelo(modelo: str) -> Path:
    return DATA_DIR / modelo

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _list_declarations(modelo: str = "349") -> list[tuple[str, Declaration]]:
    """List all saved declarations as (id, Declaration) pairs."""
    d = _data_dir_for_modelo(modelo)
    d.mkdir(parents=True, exist_ok=True)
    result = []
    for p in sorted(d.glob("*.yaml")):
        try:
            decl = load_declaration(p)
            result.append((p.stem, decl))
        except Exception:
            continue
    return result


def _get_declaration(decl_id: str, modelo: str = "349") -> Declaration | None:
    path = _data_dir_for_modelo(modelo) / f"{decl_id}.yaml"
    if path.exists():
        return load_declaration(path)
    return None


def _save_declaration(decl_id: str, decl: Declaration, modelo: str = "349") -> None:
    d = _data_dir_for_modelo(modelo)
    d.mkdir(parents=True, exist_ok=True)
    save_declaration(decl, d / f"{decl_id}.yaml")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "modelos": MODELOS,
    })


@app.get("/modelo/{modelo}", response_class=HTMLResponse)
async def modelo_index(request: Request, modelo: str):
    if modelo not in MODELOS:
        return RedirectResponse("/", status_code=303)
    declarations = _list_declarations(modelo)
    return templates.TemplateResponse(request, "modelo.html", {
        "modelo": modelo,
        "modelo_info": MODELOS[modelo],
        "declarations": declarations,
    })


@app.post("/modelo/{modelo}/declarations")
async def create_declaration(
    request: Request,
    modelo: str,
    nif: str = Form(...),
    name: str = Form(...),
    phone: str = Form(""),
    contact_name: str = Form(""),
    email: str = Form(""),
    exercise_year: int = Form(...),
    period: str = Form(...),
):
    decl = Declaration(
        exercise_year=exercise_year,
        period=period,
        declarant=Declarant(
            nif=nif,
            name=name,
            phone=phone,
            contact_name=contact_name or name,
            email=email,
        ),
    )
    decl_id = _make_filename(decl)
    _save_declaration(decl_id, decl, modelo)
    return RedirectResponse(f"/modelo/{modelo}/declarations/{decl_id}", status_code=303)


@app.get("/modelo/{modelo}/declarations/{decl_id}", response_class=HTMLResponse)
async def edit_declaration(request: Request, modelo: str, decl_id: str):
    decl = _get_declaration(decl_id, modelo)
    if not decl:
        return RedirectResponse(f"/modelo/{modelo}", status_code=303)
    return templates.TemplateResponse(request, "declaration.html", {
        "modelo": modelo,
        "decl_id": decl_id,
        "decl": decl,
    })


@app.post("/modelo/{modelo}/declarations/{decl_id}/declarant")
async def update_declarant(
    request: Request,
    modelo: str,
    decl_id: str,
    nif: str = Form(...),
    name: str = Form(...),
    phone: str = Form(""),
    contact_name: str = Form(""),
    email: str = Form(""),
    exercise_year: int = Form(...),
    period: str = Form(...),
):
    decl = _get_declaration(decl_id, modelo)
    if not decl:
        return RedirectResponse(f"/modelo/{modelo}", status_code=303)

    decl = decl.model_copy(update={
        "exercise_year": exercise_year,
        "period": period,
        "declarant": Declarant(
            nif=nif, name=name, phone=phone,
            contact_name=contact_name or name, email=email,
        ),
    })
    _save_declaration(decl_id, decl, modelo)
    return RedirectResponse(f"/modelo/{modelo}/declarations/{decl_id}", status_code=303)


@app.post("/modelo/{modelo}/declarations/{decl_id}/operators", response_class=HTMLResponse)
async def add_operator(
    request: Request,
    modelo: str,
    decl_id: str,
    country: str = Form(...),
    nif: str = Form(...),
    name: str = Form(...),
    key: str = Form(...),
    amount: str = Form(...),
):
    decl = _get_declaration(decl_id, modelo)
    if not decl:
        return HTMLResponse("Not found", status_code=404)

    op = Operator(
        country_code=country,
        nif=nif,
        name=name,
        operation_key=key,
        amount=Decimal(amount.replace(",", ".")),
    )
    operators = list(decl.operators) + [op]
    decl = decl.model_copy(update={"operators": operators})
    _save_declaration(decl_id, decl, modelo)

    return templates.TemplateResponse(request, "_operators.html", {
        "modelo": modelo,
        "decl_id": decl_id,
        "decl": decl,
    })


@app.delete("/modelo/{modelo}/declarations/{decl_id}/operators/{idx}", response_class=HTMLResponse)
async def delete_operator(request: Request, modelo: str, decl_id: str, idx: int):
    decl = _get_declaration(decl_id, modelo)
    if not decl:
        return HTMLResponse("Not found", status_code=404)

    operators = [op for i, op in enumerate(decl.operators) if i != idx]
    decl = decl.model_copy(update={"operators": operators})
    _save_declaration(decl_id, decl, modelo)

    return templates.TemplateResponse(request, "_operators.html", {
        "modelo": modelo,
        "decl_id": decl_id,
        "decl": decl,
    })


@app.post("/modelo/{modelo}/declarations/{decl_id}/generate")
async def generate(request: Request, modelo: str, decl_id: str):
    decl = _get_declaration(decl_id, modelo)
    if not decl:
        return RedirectResponse(f"/modelo/{modelo}", status_code=303)

    ext = MODELOS.get(modelo, {}).get("extension", f".{modelo}")
    filename = _make_filename(decl)
    tmp_file = Path(f"/tmp/{filename}{ext}")
    write_349(decl, output_path=tmp_file)

    data = tmp_file.read_bytes()
    return StreamingResponse(
        BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}{ext}"'},
    )


@app.post("/modelo/{modelo}/import")
async def import_file(request: Request, modelo: str, file: UploadFile = File(...)):
    content = await file.read()
    ext = MODELOS.get(modelo, {}).get("extension", f".{modelo}")
    tmp_path = Path(f"/tmp/import_{uuid.uuid4().hex}{ext}")
    tmp_path.write_bytes(content)

    try:
        decl = parse_349(tmp_path)
        decl_id = _make_filename(decl)
        _save_declaration(decl_id, decl, modelo)
        return RedirectResponse(f"/modelo/{modelo}/declarations/{decl_id}", status_code=303)
    finally:
        tmp_path.unlink(missing_ok=True)


@app.delete("/modelo/{modelo}/declarations/{decl_id}")
async def delete_declaration(request: Request, modelo: str, decl_id: str):
    path = _data_dir_for_modelo(modelo) / f"{decl_id}.yaml"
    path.unlink(missing_ok=True)
    return HTMLResponse("")
