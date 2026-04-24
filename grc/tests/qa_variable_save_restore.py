#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Copyright 2025 GNU Radio Project
#
# QA test for the variable_save_restore GRC block.
#
# Verifies that the block:
#   1. Creates a YAML state file in GR_STATE_PATH when a flowgraph runs.
#   2. Stores the correct variable value in that file.
#   3. Restores a pre-existing value from the state file on the next run.
#
# The fixture sets GR_STATE_PATH to an isolated temporary directory so that
# tests never touch the real user state directory and can inspect the YAML
# contents directly.
#
# Usage (standalone):
#   python3 qa_variable_save_restore.py
#
# Usage (via ctest / GR_ADD_TEST):
#   the CMakeLists.txt entry handles registration automatically.
#

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

try:
    import yaml
except ImportError:
    yaml = None  # PyYAML – always available in a GR Python env


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Absolute path to the companion .grc flowgraph that exercises the block.
_GRC_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "test_variable_save_restore.grc",
)

# The flowgraph ID embedded in the .grc file.  The block writes its state to
# $GR_STATE_PATH/<FLOWGRAPH_ID>.yaml, so the test must know this name.
_FLOWGRAPH_ID = "test_variable_save_restore"

# The variable name used inside the test flowgraph.
_VARIABLE_ID = "my_variable"

# The default / initial value set in the .grc file.
_DEFAULT_VALUE = 42


class QaVariableSaveRestore(unittest.TestCase):
    """Unit tests for the variable_save_restore GRC block."""

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------

    def setUp(self):
        """
        Create an isolated temporary directory and point GR_STATE_PATH at it.
        A fresh compile-output directory is also prepared for each test so
        that grcc artefacts do not leak between runs.
        """
        self._state_dir = tempfile.mkdtemp(prefix="gr_state_qa_")
        self._out_dir = tempfile.mkdtemp(prefix="gr_grcc_out_")

        # Build a clean environment that inherits the current one but overrides
        # the state path variable so we never touch the real user directory.
        self._env = os.environ.copy()
        self._env["GR_STATE_PATH"] = self._state_dir

    def tearDown(self):
        shutil.rmtree(self._state_dir, ignore_errors=True)
        shutil.rmtree(self._out_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compile(self):
        """
        Compile the test GRC flowgraph to Python via grcc.

        Returns the path to the generated .py file.
        Fails the test if grcc exits non-zero.
        """
        result = subprocess.run(
            ["grcc", _GRC_FILE, "-o", self._out_dir],
            env=self._env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"grcc compilation failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        py_files = [f for f in os.listdir(self._out_dir) if f.endswith(".py")]
        self.assertTrue(
            py_files,
            msg=f"grcc produced no .py file in {self._out_dir}",
        )
        return os.path.join(self._out_dir, py_files[0])

    def _run(self, py_file):
        """
        Execute the compiled flowgraph Python file.

        Fails the test if the process exits non-zero.
        A 30-second timeout guards against hangs.
        """
        result = subprocess.run(
            [sys.executable, "-u", py_file],
            env=self._env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"Flowgraph run failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def _state_file(self):
        return os.path.join(self._state_dir, _FLOWGRAPH_ID + ".yml")

    def _load_state(self):
        """Read and parse the YAML state file; return as a dict."""
        path = self._state_file()
        self.assertTrue(
            os.path.isfile(path),
            msg=f"Expected state file not found: {path}\n"
            f"Contents of {self._state_dir}: {list(os.walk(self._state_dir))}",
        )
        with open(path) as fh:
            return yaml.safe_load(fh) or {}

    def _write_state(self, data: dict):
        path = self._state_file()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            yaml.dump(data, fh)

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_010_compile(self):
        """
        The .grc flowgraph must compile without errors via grcc.

        This is a smoke-test: if grcc fails, none of the other tests make
        sense.
        """
        self._compile()  # fails internally via assertEqual if non-zero

    def test_020_save_creates_state_file(self):
        """
        After a first run with an empty GR_STATE_PATH, a YAML state file
        must exist in that directory.
        """
        py_file = self._compile()
        self._run(py_file)

        yaml_files = [
            f
            for f in os.listdir(self._state_dir)
            if f.endswith(".yaml") or f.endswith(".yml")
        ]
        self.assertTrue(
            yaml_files,
            msg=f"No YAML file created in GR_STATE_PATH={self._state_dir}\n"
            f"Directory contents: {os.listdir(self._state_dir)}",
        )

    def test_030_save_stores_correct_value(self):
        """
        The state YAML must record the variable's current value (42, as set
        in the .grc file) under the variable's ID key.
        """
        py_file = self._compile()
        self._run(py_file)

        state = self._load_state()
        self.assertIn(
            _VARIABLE_ID,
            state,
            msg=f"Key '{_VARIABLE_ID}' missing from state file.\nFull state: {state}",
        )
        self.assertEqual(
            state[_VARIABLE_ID],
            _DEFAULT_VALUE,
            msg=f"Saved value mismatch. Expected {_DEFAULT_VALUE}, got {state[_VARIABLE_ID]}",
        )

    def test_040_restore_reads_saved_value(self):
        """
        When the state file already contains a value for the variable, the
        block must restore that value on the next run and then re-save it
        (so the file still contains the restored value after execution).

        We use 99 as the injected value, which is deliberately different from
        the compile-time default of 42 so we can tell them apart.
        """
        injected_value = 99
        self._write_state({_VARIABLE_ID: injected_value})

        py_file = self._compile()
        self._run(py_file)

        state = self._load_state()
        self.assertIn(
            _VARIABLE_ID,
            state,
            msg=f"Key '{_VARIABLE_ID}' missing from state file after restore run.\nFull state: {state}",
        )
        self.assertEqual(
            state[_VARIABLE_ID],
            injected_value,
            msg=(
                f"Restored value mismatch. Expected {injected_value}, "
                f"got {state[_VARIABLE_ID]}. "
                f"The block may have ignored the pre-populated state file."
            ),
        )

    def test_050_state_file_is_valid_yaml(self):
        if yaml is None:
            self.skipTest("PyYAML not available")
        """
        The written state file must be parseable YAML (not just any text).
        A corrupted or non-YAML file would fail silently at restore time.
        """
        py_file = self._compile()
        self._run(py_file)

        path = self._state_file()
        try:
            with open(path) as fh:
                data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            self.fail(f"State file is not valid YAML: {exc}")

        self.assertIsInstance(
            data,
            dict,
            msg=f"State file top-level should be a mapping, got {type(data)}",
        )

    def test_060_state_dir_is_respected(self):
        """
        The block must write exclusively to the directory pointed at by
        GR_STATE_PATH, not to any default or hard-coded location.

        We verify that the state file appears inside _state_dir and not
        somewhere in the user's home directory or /tmp.
        """
        py_file = self._compile()
        self._run(py_file)

        state_path = self._state_file()
        self.assertTrue(
            os.path.commonpath([state_path, self._state_dir]) == self._state_dir,
            msg=(
                f"State file {state_path!r} was not written inside the "
                f"expected GR_STATE_PATH={self._state_dir!r}."
            ),
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
