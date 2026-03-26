# CLAUDE.md

## Project

YABILABB - Bizkaia tax modelo file generator replacing BILA. Python 3.12+, src layout.

## Commands

```bash
uv venv && uv pip install -e ".[web,dev]"   # install
pytest                                       # run tests (12 tests, ~0.1s)
yabilabb generate data/example_input.yaml    # generate .349 from YAML
yabilabb parse examples/*.349 -o out.yaml    # parse BILA file to YAML
yabilabb serve                               # web UI on :8000
```

## Architecture

- **records.py** is the critical file - 500-char fixed-width record generation per BOB 2020 spec. Field positions are 1-indexed matching the regulation. Tests verify byte-for-byte against real BILA output.
- **envelope.py** uses string templates (not XML libs) because BILA's format has strict formatting (CRLF, single-quoted attrs, self-closing tags with space before `/>`) that XML libraries would normalize.
- **writer.py** produces ZIP files with `.tmp` inside. Filename convention drops the NIF prefix letter (e.g., `B12345678` -> `12345678` in filename).
- **web/app.py** routes are scoped by modelo: `/modelo/{code}/declarations/...`. Uses htmx for operator table CRUD. Starlette 1.0 `TemplateResponse(request, name, context)` signature.
- Amounts stored as `Decimal`, converted to integer cents for records.

## Spec source

BOB 2020-03-11 Orden Foral 570/2020, Anexo II (pages 14-27):
https://www.bizkaia.eus/lehendakaritza/Bao_bob/2020/03/11/I-197_cas.pdf

## Sensitive data

The `examples/` and `data/` directories may contain real personal/financial data and are gitignored. Never commit files from them.
