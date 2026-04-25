#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
"""
tests/test_expr_utils.py
========================
Unit tests for grc/core/generator/expr_utils.py (fix for issue #8071).

Run with:
    python -m pytest tests/test_expr_utils.py -v
or:
    python tests/test_expr_utils.py
"""

import sys
import os

# Allow running from repo root without installing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from grc.core.generator.expr_utils import (
    is_composite_expr,
    parenthesize_if_composite,
)

import unittest


class TestIsCompositeExpr(unittest.TestCase):
    """Tests for is_composite_expr()."""

    # ── Atomic (should NOT be composite) ─────────────────────────────────────

    def test_simple_name(self):
        self.assertFalse(is_composite_expr("N"))

    def test_simple_name_samp_rate(self):
        self.assertFalse(is_composite_expr("samp_rate"))

    def test_integer_literal(self):
        self.assertFalse(is_composite_expr("32000"))

    def test_float_literal(self):
        self.assertFalse(is_composite_expr("3.14"))

    def test_attribute_access(self):
        """gr.sizeof_float is an attribute – should be atomic."""
        self.assertFalse(is_composite_expr("gr.sizeof_float"))

    def test_deep_attribute(self):
        self.assertFalse(is_composite_expr("self.N"))

    def test_function_call(self):
        """A call already carries its own parentheses."""
        self.assertFalse(is_composite_expr("int(x)"))

    def test_function_call_with_args(self):
        self.assertFalse(is_composite_expr("range(0, N, 2)"))

    def test_subscript(self):
        self.assertFalse(is_composite_expr("arr[0]"))

    def test_empty_string(self):
        self.assertFalse(is_composite_expr(""))

    def test_whitespace_only(self):
        self.assertFalse(is_composite_expr("   "))

    def test_invalid_python(self):
        """Invalid Python should not raise – return False (leave unchanged)."""
        self.assertFalse(is_composite_expr("!!!"))

    # ── Composite (should be detected) ───────────────────────────────────────

    def test_addition(self):
        self.assertTrue(is_composite_expr("M + N"))

    def test_addition_no_spaces(self):
        self.assertTrue(is_composite_expr("M+N"))

    def test_subtraction(self):
        self.assertTrue(is_composite_expr("N - 1"))

    def test_multiplication(self):
        self.assertTrue(is_composite_expr("N * 2"))

    def test_division(self):
        self.assertTrue(is_composite_expr("N / 2"))

    def test_integer_division(self):
        self.assertTrue(is_composite_expr("N // 2"))

    def test_modulo(self):
        self.assertTrue(is_composite_expr("N % 2"))

    def test_power(self):
        self.assertTrue(is_composite_expr("2 ** 10"))

    def test_combined_expression(self):
        self.assertTrue(is_composite_expr("N * 2 - 1"))

    def test_unary_minus(self):
        """Unary negation is also a composite – wrapping is safer."""
        self.assertTrue(is_composite_expr("-N"))

    def test_unary_not(self):
        self.assertTrue(is_composite_expr("not flag"))

    def test_boolean_and(self):
        self.assertTrue(is_composite_expr("a and b"))

    def test_boolean_or(self):
        self.assertTrue(is_composite_expr("a or b"))

    def test_comparison(self):
        self.assertTrue(is_composite_expr("N > 0"))

    def test_ternary(self):
        self.assertTrue(is_composite_expr("a if cond else b"))

    def test_bitwise_or(self):
        self.assertTrue(is_composite_expr("a | b"))

    def test_bitwise_and(self):
        self.assertTrue(is_composite_expr("a & b"))

    def test_shift(self):
        self.assertTrue(is_composite_expr("N << 2"))

    def test_leading_trailing_spaces_preserved(self):
        """Whitespace around a composite expression must not confuse detection."""
        self.assertTrue(is_composite_expr("  M + N  "))


class TestParenthesizeIfComposite(unittest.TestCase):
    """Tests for parenthesize_if_composite() – the main API."""

    # ── Atomic inputs – must be returned unchanged ────────────────────────────

    def test_simple_name_unchanged(self):
        self.assertEqual(parenthesize_if_composite("N"), "N")

    def test_literal_unchanged(self):
        self.assertEqual(parenthesize_if_composite("32000"), "32000")

    def test_attribute_unchanged(self):
        self.assertEqual(
            parenthesize_if_composite("gr.sizeof_float"), "gr.sizeof_float"
        )

    def test_call_unchanged(self):
        self.assertEqual(parenthesize_if_composite("int(x)"), "int(x)")

    def test_empty_string_unchanged(self):
        self.assertEqual(parenthesize_if_composite(""), "")

    def test_whitespace_unchanged(self):
        """Whitespace-only strings can't be parsed – return as-is."""
        self.assertEqual(parenthesize_if_composite("   "), "   ")

    def test_invalid_python_unchanged(self):
        self.assertEqual(parenthesize_if_composite("!!!"), "!!!")

    # ── Composite inputs – must be wrapped ───────────────────────────────────

    def test_addition_wrapped(self):
        self.assertEqual(parenthesize_if_composite("M + N"), "(M + N)")

    def test_addition_no_spaces_wrapped(self):
        self.assertEqual(parenthesize_if_composite("M+N"), "(M+N)")

    def test_subtraction_wrapped(self):
        self.assertEqual(parenthesize_if_composite("N - 1"), "(N - 1)")

    def test_multiplication_wrapped(self):
        self.assertEqual(parenthesize_if_composite("N * 2"), "(N * 2)")

    def test_complex_expr_wrapped(self):
        self.assertEqual(
            parenthesize_if_composite("N * 2 - 1"), "(N * 2 - 1)"
        )

    def test_unary_minus_wrapped(self):
        self.assertEqual(parenthesize_if_composite("-N"), "(-N)")

    def test_ternary_wrapped(self):
        self.assertEqual(
            parenthesize_if_composite("a if cond else b"),
            "(a if cond else b)",
        )

    # ── Integration: simulates what GRC codegen does ─────────────────────────

    def test_issue_8071_scenario(self):
        """
        Reproduces the exact scenario from issue #8071.

        Template: "blocks.null_sink(gr.sizeof_gr_complex*${vlen})"
        vlen value in GRC: "M+N"

        Before fix → blocks.null_sink(gr.sizeof_gr_complex*M+N)   WRONG
        After fix  → blocks.null_sink(gr.sizeof_gr_complex*(M+N))  CORRECT
        """
        template = "blocks.null_sink(gr.sizeof_gr_complex*${vlen})"
        vlen_raw = "M+N"

        # Old (buggy) behaviour:
        buggy = template.replace("${vlen}", vlen_raw)
        self.assertEqual(buggy, "blocks.null_sink(gr.sizeof_gr_complex*M+N)")

        # New (fixed) behaviour:
        safe_vlen = parenthesize_if_composite(vlen_raw)
        fixed = template.replace("${vlen}", safe_vlen)
        self.assertEqual(
            fixed, "blocks.null_sink(gr.sizeof_gr_complex*(M+N))"
        )

    def test_issue_8071_stream_to_vector(self):
        """
        The stream_to_vector line from the issue – vlen is the last argument,
        so no precedence problem; wrapping is harmless.
        """
        template = "blocks.stream_to_vector(gr.sizeof_gr_complex*1, ${vlen})"
        vlen_raw = "M+N"
        safe_vlen = parenthesize_if_composite(vlen_raw)
        result = template.replace("${vlen}", safe_vlen)
        self.assertEqual(
            result,
            "blocks.stream_to_vector(gr.sizeof_gr_complex*1, (M+N))",
        )

    def test_simple_name_no_extra_parens(self):
        """
        Atomic vlen should not get extra parentheses – keeps generated code
        clean and readable.
        """
        template = "blocks.null_sink(gr.sizeof_gr_complex*${vlen})"
        vlen_raw = "N"
        safe_vlen = parenthesize_if_composite(vlen_raw)
        result = template.replace("${vlen}", safe_vlen)
        self.assertEqual(result, "blocks.null_sink(gr.sizeof_gr_complex*N)")

    def test_samp_rate_no_extra_parens(self):
        template = "analog.sig_source_c(${samp_rate}, analog.GR_COS_WAVE, 1000, 1, 0, 0)"
        samp_rate_raw = "samp_rate"
        safe = parenthesize_if_composite(samp_rate_raw)
        result = template.replace("${samp_rate}", safe)
        self.assertEqual(
            result,
            "analog.sig_source_c(samp_rate, analog.GR_COS_WAVE, 1000, 1, 0, 0)",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
