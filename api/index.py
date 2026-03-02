from __future__ import annotations

from fractions import Fraction
import re
from typing import Dict, List, Tuple

from flask import Flask, render_template, request
import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

app = Flask(__name__)

TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)


def parse_numeric_expression(value: str) -> Fraction:
    try:
        expr = parse_expr(value, transformations=TRANSFORMATIONS, evaluate=True)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"No se pudo interpretar '{value}' como numero.") from exc

    simplified = sp.nsimplify(expr)
    if simplified.free_symbols:
        raise ValueError(f"'{value}' contiene simbolos, se esperaba un numero.")

    if simplified.is_Rational:
        return Fraction(int(simplified.p), int(simplified.q))

    try:
        rational = sp.Rational(simplified)
        return Fraction(int(rational.p), int(rational.q))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"'{value}' no es un numero racional valido.") from exc


def parse_augmented_matrix(text: str) -> List[List[Fraction]]:
    rows: List[List[Fraction]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        tokens = [token for token in re.split(r"[\s,]+", line) if token]
        if not tokens:
            continue
        rows.append([parse_numeric_expression(token) for token in tokens])

    if not rows:
        raise ValueError("La matriz esta vacia.")

    width = len(rows[0])
    if width < 2:
        raise ValueError("La matriz aumentada debe tener al menos 2 columnas.")

    for row in rows:
        if len(row) != width:
            raise ValueError("Todas las filas de la matriz deben tener el mismo largo.")

    return rows


def parse_equations(
    equations_text: str,
    variables_text: str,
) -> Tuple[List[List[Fraction]], List[str]]:
    equations: List[sp.Equality] = []
    for raw_line in equations_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if "=" in line:
            left, right = line.split("=", 1)
        else:
            left, right = line, "0"

        try:
            left_expr = parse_expr(
                left,
                transformations=TRANSFORMATIONS,
                evaluate=True,
            )
            right_expr = parse_expr(
                right,
                transformations=TRANSFORMATIONS,
                evaluate=True,
            )
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"No se pudo interpretar la ecuacion: '{line}'.") from exc

        equations.append(sp.Eq(left_expr, right_expr))

    if not equations:
        raise ValueError("No se encontraron ecuaciones para procesar.")

    if variables_text.strip():
        names = [name for name in re.split(r"[\s,]+", variables_text.strip()) if name]
        variables = [sp.Symbol(name) for name in names]
    else:
        inferred = sorted(
            {symbol for eq in equations for symbol in eq.free_symbols},
            key=lambda symbol: symbol.name,
        )
        if not inferred:
            raise ValueError("No se pudieron inferir variables desde las ecuaciones.")
        variables = inferred

    try:
        matrix_a, vector_b = sp.linear_eq_to_matrix(equations, variables)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            "No se pudo convertir el sistema a matriz lineal. "
            "Verifica que las ecuaciones sean lineales."
        ) from exc

    augmented: List[List[Fraction]] = []
    for row_index in range(matrix_a.rows):
        row: List[Fraction] = []
        for col_index in range(matrix_a.cols):
            row.append(parse_numeric_expression(str(matrix_a[row_index, col_index])))
        row.append(parse_numeric_expression(str(vector_b[row_index, 0])))
        augmented.append(row)

    return augmented, [str(variable) for variable in variables]


def clone_matrix(matrix: List[List[Fraction]]) -> List[List[Fraction]]:
    return [row[:] for row in matrix]


def format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def fraction_to_latex(value: Fraction) -> str:
    numerator = value.numerator
    denominator = value.denominator
    if denominator == 1:
        return str(numerator)
    sign = "-" if numerator < 0 else ""
    return f"{sign}\\frac{{{abs(numerator)}}}{{{denominator}}}"


def matrix_to_latex(matrix: List[List[Fraction]], augmented: bool = True) -> str:
    if not matrix:
        return r"\left[\right]"

    columns = len(matrix[0])
    if augmented and columns > 1:
        spec = "c" * (columns - 1) + "|c"
    else:
        spec = "c" * columns

    body = r" \\ ".join(
        " & ".join(fraction_to_latex(value) for value in row) for row in matrix
    )
    return rf"\left[\begin{{array}}{{{spec}}}{body}\end{{array}}\right]"


def normalize_row(row: List[Fraction], factor: Fraction) -> List[Fraction]:
    return [value * factor for value in row]


def combine_rows(
    target_row: List[Fraction],
    source_row: List[Fraction],
    factor: Fraction,
) -> List[Fraction]:
    return [target - factor * source for target, source in zip(target_row, source_row)]


def replacement_operation_text(
    target: int,
    source: int,
    factor: Fraction,
) -> Tuple[str, str]:
    if factor == 0:
        return "", ""

    if factor > 0:
        symbol_text = "-"
        symbol_latex = "-"
    else:
        symbol_text = "+"
        symbol_latex = "+"

    abs_factor = abs(factor)
    factor_text = format_fraction(abs_factor)
    factor_latex = fraction_to_latex(abs_factor)

    if abs_factor == 1:
        source_text = f"R{source}"
        source_latex = rf"R_{{{source}}}"
    else:
        source_text = f"{factor_text}*R{source}"
        source_latex = rf"{factor_latex}R_{{{source}}}"

    op_text = f"R{target} <- R{target} {symbol_text} {source_text}"
    op_latex = rf"R_{{{target}}} \leftarrow R_{{{target}}} {symbol_latex} {source_latex}"
    return op_text, op_latex


def rref_with_steps(matrix: List[List[Fraction]]) -> Tuple[List[List[Fraction]], List[Dict[str, str]]]:
    work = clone_matrix(matrix)
    steps: List[Dict[str, str]] = []

    row_count = len(work)
    col_count = len(work[0]) if row_count > 0 else 0

    lead = 0
    for row in range(row_count):
        if lead >= col_count:
            break

        pivot_row = row
        while pivot_row < row_count and work[pivot_row][lead] == 0:
            pivot_row += 1

        while pivot_row == row_count:
            lead += 1
            if lead >= col_count:
                return work, steps
            pivot_row = row
            while pivot_row < row_count and work[pivot_row][lead] == 0:
                pivot_row += 1

        if pivot_row != row:
            work[row], work[pivot_row] = work[pivot_row], work[row]
            steps.append(
                {
                    "operation_text": f"Intercambio R{row + 1} <-> R{pivot_row + 1}",
                    "operation_latex": rf"R_{{{row + 1}}} \leftrightarrow R_{{{pivot_row + 1}}}",
                    "matrix_latex": matrix_to_latex(work),
                }
            )

        pivot = work[row][lead]
        if pivot != 1:
            factor = Fraction(1, 1) / pivot
            work[row] = normalize_row(work[row], factor)
            steps.append(
                {
                    "operation_text": f"R{row + 1} <- ({format_fraction(factor)})*R{row + 1}",
                    "operation_latex": rf"R_{{{row + 1}}} \leftarrow {fraction_to_latex(factor)}R_{{{row + 1}}}",
                    "matrix_latex": matrix_to_latex(work),
                }
            )

        for other_row in range(row_count):
            if other_row == row:
                continue
            factor = work[other_row][lead]
            if factor == 0:
                continue

            work[other_row] = combine_rows(work[other_row], work[row], factor)
            operation_text, operation_latex = replacement_operation_text(
                other_row + 1,
                row + 1,
                factor,
            )
            steps.append(
                {
                    "operation_text": operation_text,
                    "operation_latex": operation_latex,
                    "matrix_latex": matrix_to_latex(work),
                }
            )

        lead += 1

    return work, steps


@app.route("/", methods=["GET", "POST"])
def index():
    context = {
        "mode": "matrix",
        "matrix_input": "1, 2, -1, 3\n2, 4, 1, 9\n-1, 2, 3, 1",
        "equations_input": "x + 2y - z = 3\n2x + 4y + z = 9\n-x + 2y + 3z = 1",
        "variables_input": "x, y, z",
        "error": "",
        "steps": [],
        "initial_matrix_latex": "",
        "final_matrix_latex": "",
        "variables_used": [],
    }

    if request.method == "POST":
        mode = request.form.get("mode", "matrix").strip().lower()
        matrix_input = request.form.get("matrix_input", "")
        equations_input = request.form.get("equations_input", "")
        variables_input = request.form.get("variables_input", "")

        context.update(
            {
                "mode": mode,
                "matrix_input": matrix_input,
                "equations_input": equations_input,
                "variables_input": variables_input,
            }
        )

        try:
            if mode == "equations":
                matrix, variables_used = parse_equations(equations_input, variables_input)
                context["variables_used"] = variables_used
            else:
                matrix = parse_augmented_matrix(matrix_input)

            reduced_matrix, steps = rref_with_steps(matrix)
            context["initial_matrix_latex"] = matrix_to_latex(matrix)
            context["final_matrix_latex"] = matrix_to_latex(reduced_matrix)
            context["steps"] = steps
        except ValueError as error:
            context["error"] = str(error)
        except Exception as error:  # noqa: BLE001
            context["error"] = f"Ocurrio un error inesperado: {error}"

    return render_template("index.html", **context)


if __name__ == "__main__":
    app.run(debug=True)
