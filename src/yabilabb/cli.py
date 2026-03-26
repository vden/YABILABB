"""CLI entry point for YABILABB."""

import argparse
import sys
from pathlib import Path

from yabilabb import __version__

# Registry of supported modelos. Each entry maps modelo code to its
# generate/parse functions. New modelos plug in here.
MODELOS = {
    "349": {
        "name": "Resumen recapitulativo de operaciones intracomunitarias",
        "extension": ".349",
    },
}


def _detect_modelo(path: Path) -> str:
    """Detect modelo from file extension or YAML content."""
    ext = path.suffix.lstrip(".")
    if ext in MODELOS:
        return ext

    # Try reading YAML to find modelo key
    if path.suffix in (".yaml", ".yml"):
        import yaml
        data = yaml.safe_load(path.read_text())
        if "modelo" in data:
            return str(data["modelo"])

    # Default to 349 for now
    return "349"


def cmd_generate(args: argparse.Namespace) -> None:
    from yabilabb.yaml_io import load_declaration
    from yabilabb.writer import write_349

    input_path = Path(args.input)
    modelo = args.modelo or _detect_modelo(input_path)

    if modelo != "349":
        print(f"Modelo {modelo} not yet implemented.", file=sys.stderr)
        sys.exit(1)

    decl = load_declaration(input_path)
    output = Path(args.output) if args.output else None
    result = write_349(decl, output)
    print(f"Generated: {result}")
    print(f"  Modelo: {modelo}")
    print(f"  Year: {decl.exercise_year}, Period: {decl.period}")
    print(f"  Declarant: {decl.declarant.nif} {decl.declarant.name}")
    print(f"  Operators: {decl.num_operators}, Total: {decl.total_amount}")
    if decl.rectifications:
        print(f"  Rectifications: {decl.num_rectifications}, Total: {decl.total_rectified_amount}")


def cmd_parse(args: argparse.Namespace) -> None:
    from yabilabb.parser import parse_349
    from yabilabb.yaml_io import save_declaration

    input_path = Path(args.input)
    modelo = args.modelo or _detect_modelo(input_path)

    if modelo != "349":
        print(f"Modelo {modelo} not yet implemented.", file=sys.stderr)
        sys.exit(1)

    decl = parse_349(input_path)
    print(f"Parsed: {args.input}")
    print(f"  Modelo: {modelo}")
    print(f"  Year: {decl.exercise_year}, Period: {decl.period}")
    print(f"  Declarant: {decl.declarant.nif} {decl.declarant.name}")
    print(f"  Operators: {decl.num_operators}, Total: {decl.total_amount}")
    if decl.rectifications:
        print(f"  Rectifications: {decl.num_rectifications}")

    if args.output:
        save_declaration(decl, Path(args.output))
        print(f"  Saved to: {args.output}")


def cmd_list_modelos(args: argparse.Namespace) -> None:
    print("Supported modelos:")
    for code, info in MODELOS.items():
        print(f"  {code} - {info['name']}")


def cmd_serve(args: argparse.Namespace) -> None:
    try:
        import uvicorn
    except ImportError:
        print("Web dependencies not installed. Run: uv pip install -e '.[web]'", file=sys.stderr)
        sys.exit(1)

    from yabilabb.web.app import app
    uvicorn.run(app, host=args.host, port=args.port)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="yabilabb",
        description="YABILABB - Yet Another BILA But Better",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # generate
    gen = sub.add_parser("generate", help="Generate declaration file from YAML")
    gen.add_argument("input", help="Input YAML file")
    gen.add_argument("-m", "--modelo", help="Modelo number (auto-detected if omitted)")
    gen.add_argument("-o", "--output", help="Output file path")

    # parse
    par = sub.add_parser("parse", help="Parse declaration file to YAML")
    par.add_argument("input", help="Input declaration file")
    par.add_argument("-m", "--modelo", help="Modelo number (auto-detected if omitted)")
    par.add_argument("-o", "--output", help="Output YAML file path")

    # modelos
    sub.add_parser("modelos", help="List supported modelos")

    # serve
    srv = sub.add_parser("serve", help="Start web UI")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()

    commands = {
        "generate": cmd_generate,
        "parse": cmd_parse,
        "modelos": cmd_list_modelos,
        "serve": cmd_serve,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
