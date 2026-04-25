# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# Copyright 2025 The GNU Radio Foundation
#
"""
expr_utils.py  –  Expression-parenthesization helpers for GRC Python codegen.

Fix for GitHub issue #8071:
  When a GRC block parameter is a composite expression (e.g. ``M + N``),
  the template substitution produces code like::

      blocks.null_sink(gr.sizeof_gr_complex*M+N)

  which is evaluated as ``(gr.sizeof_gr_complex * M) + N`` – wrong.

  The correct output is::

      blocks.null_sink(gr.sizeof_gr_complex*(M+N))

  This module provides :func:`parenthesize_if_composite` which uses
  Python's built-in ``ast`` module to detect whether a string is a
  *composite* expression (i.e. something more than a single name, number,
  attribute, or call) and, if so, wraps it in parentheses.

Usage inside the Mako template or Python generator::

    from gnuradio.grc.core.generator.expr_utils import parenthesize_if_composite

    # In a Mako template:
    gr.sizeof_float * ${parenthesize_if_composite(vlen)}

    # Or equivalently in Python:
    f"gr.sizeof_float * {parenthesize_if_composite(vlen_expr)}"
"""

import ast

__all__ = ["parenthesize_if_composite", "is_composite_expr"]


# ---------------------------------------------------------------------------
# Node types that are "atomic" – safe to use without extra parens anywhere.
# ---------------------------------------------------------------------------
_ATOMIC_TYPES = (
    ast.Constant,    # numeric / string literals
    ast.Name,        # bare identifiers: samp_rate, N, M, …
    ast.Attribute,   # dotted names: gr.sizeof_float, self.N, …
    ast.Subscript,   # indexed access: arr[0]
    ast.Call,        # function calls: int(x)  – already has its own parens
)


def is_composite_expr(expr_str: str) -> bool:
    """Return *True* if *expr_str* is a composite (non-atomic) Python expression.

    A composite expression is one that contains operators (binary, unary,
    boolean, comparison, ternary, etc.) at the top level, meaning it would
    change meaning if its operator precedence were altered by surrounding
    context.

    Returns *False* for atomic expressions and for strings that cannot be
    parsed as valid Python (they are left unchanged by the caller).

    Examples
    --------
    >>> is_composite_expr("N")
    False
    >>> is_composite_expr("3.14")
    False
    >>> is_composite_expr("gr.sizeof_float")
    False
    >>> is_composite_expr("int(x)")
    False
    >>> is_composite_expr("M + N")
    True
    >>> is_composite_expr("N * 2 - 1")
    True
    >>> is_composite_expr("-N")
    True
    >>> is_composite_expr("a if cond else b")
    True
    """
    expr_str = expr_str.strip()
    if not expr_str:
        return False
    try:
        tree = ast.parse(expr_str, mode="eval")
    except SyntaxError:
        # Not valid Python – leave it alone.
        return False
    return not isinstance(tree.body, _ATOMIC_TYPES)


def parenthesize_if_composite(expr_str: str) -> str:
    """Wrap *expr_str* in parentheses if it is a composite expression.

    This is the main entry-point used by the GRC Python code generator to
    ensure that parameter expressions are never subject to unintended
    operator-precedence interactions with surrounding generated code.

    Parameters
    ----------
    expr_str:
        The raw string from the GRC parameter entry box.

    Returns
    -------
    str
        The original string if it is atomic or invalid Python; otherwise
        the string wrapped in ``(…)``.

    Examples
    --------
    >>> parenthesize_if_composite("N")
    'N'
    >>> parenthesize_if_composite("M + N")
    '(M + N)'
    >>> parenthesize_if_composite("gr.sizeof_float")
    'gr.sizeof_float'
    >>> parenthesize_if_composite("N * 2 - 1")
    '(N * 2 - 1)'
    >>> parenthesize_if_composite("  ")
    '  '
    """
    if is_composite_expr(expr_str):
        return f"({expr_str})"
    return expr_str
