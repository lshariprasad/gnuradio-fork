# Contribution Report: QA Test for `variable_save_restore` Block
## Closes #8095 · PR for branch `blocks/add-qa-variable-save-restore`

---

### What this PR adds

Three files under `grc/tests/`:

| File | Purpose |
|------|---------|
| `qa_variable_save_restore.py` | Python `unittest` test suite (6 test cases) |
| `test_variable_save_restore.grc` | Minimal no-GUI GRC flowgraph that exercises the block |
| `CMakeLists.txt` | Registers the test with CTest via `GR_ADD_TEST` |

---

### How the test works

**Fixture (setUp / tearDown)**

Each test case creates two isolated `tempfile.mkdtemp()` directories:

- `_state_dir` – pointed at by `GR_STATE_PATH` so the block never touches the
  real user state directory.
- `_out_dir` – where `grcc` writes the compiled Python flowgraph.

Both directories are deleted in `tearDown` regardless of test outcome.

**Test sequence**

```
1.  grcc  test_variable_save_restore.grc  -o  <_out_dir>
                     ↓
          <_out_dir>/test_variable_save_restore.py   (generated Python)
                     ↓
2.  python3  test_variable_save_restore.py
         GR_STATE_PATH=<_state_dir>
                     ↓
3.  Assert: <_state_dir>/test_variable_save_restore.yaml  exists
            state['my_variable'] == 42                    (save test)
            state['my_variable'] == 99   (after pre-seeding with 99) (restore test)
```

**Test cases**

| ID | Name | What it checks |
|----|------|---------------|
| `test_010_compile` | Smoke | `grcc` exits 0 |
| `test_020_save_creates_state_file` | Save – file exists | A YAML file is created in `GR_STATE_PATH` |
| `test_030_save_stores_correct_value` | Save – value correct | `state['my_variable'] == 42` |
| `test_040_restore_reads_saved_value` | Restore | Block reads pre-seeded value (99) instead of default (42) |
| `test_050_state_file_is_valid_yaml` | YAML validity | `yaml.safe_load()` succeeds; top-level is a dict |
| `test_060_state_dir_is_respected` | Path isolation | State file path is inside `GR_STATE_PATH`, nowhere else |

---

### Environment variable used

Per maintainer comment on [commit 43ff3a8](https://github.com/gnuradio/gnuradio/commit/43ff3a8):

```python
# correct – used in this PR
os.environ["GR_STATE_PATH"] = self._state_dir

# NOT used – superseded by GR_STATE_PATH
# os.environ["GR_PREFS_PATH"] = ...
```

---

### Running the test locally

```bash
# One-shot (no build required):
GR_STATE_PATH=/tmp/test_state python3 grc/tests/qa_variable_save_restore.py

# Via CTest after building:
cd build
ctest -V -R qa_variable_save_restore
```

---

### Files changed

```
grc/tests/
├── CMakeLists.txt                    ← new  (GR_ADD_TEST registration)
├── qa_variable_save_restore.py       ← new  (6 unittest test cases)
└── test_variable_save_restore.grc    ← new  (test flowgraph fixture)
```

No existing files were modified.

---

### Checklist

- [x] `GR_STATE_PATH` is set to a temp directory in `setUp`; cleaned up in `tearDown`
- [x] Test does **not** require an active display (flowgraph uses `generate_options: no_gui`)
- [x] Both save and restore paths are explicitly tested
- [x] YAML validity is asserted independently of value correctness
- [x] Path isolation is verified (block must not write outside `GR_STATE_PATH`)
- [x] `CMakeLists.txt` registers the test via `GR_ADD_TEST`
- [x] `.grc` fixture file installed alongside test script for in-tree and installed runs
