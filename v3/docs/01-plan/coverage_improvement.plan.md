# Test Coverage Improvement Plan

> **Status**: ✅ Completed (2026-05-19 확인)  
> 계획된 `tests/run_tests.py`, `tests/unit/`, `tests/integration/` 구조가 모두 구축되었고
> 65개 테스트가 통과한다. 본 문서는 참조용으로 보존한다.

## Goal

Increase test coverage from ~40% to 60% by implementing structured Unit and Integration tests.
Focus on Core Business Logic and the newly refactored UI Panels.

## Testing Strategy

- **Framework**: `unittest` (Standard Python Library)
- **Runner**: New `tests/run_tests.py` to auto-discover and run all tests.
- **Mocking**: `unittest.mock` for isolating components (e.g., mocking DB or UI parents).

## Target Areas

### 1. Core Logic (Models & Utils) - HIGH PRIORITY

- **`models/data_manager.py`**: Test CRUD operations, LOT generation logic.
- **`utils/config_manager.py`**: Test configuration loading/saving.
- **`utils/logger.py`**: Verify logging setup (basic check).

### 2. UI Panels (Refactored Components) - HIGH PRIORITY

- **`ui/panels/recipe_panel.py`**: Test `get_amount`, `set_recipes`, signal emission.
- **`ui/panels/work_info_panel.py`**: Test date/time retrieval, worker validation.
- **`ui/panels/material_table_panel.py`**: Test data collection, incomplete input validation.
- **`ui/panels/scan_effects_panel.py`**: Test default loading/saving logic.

### 3. Integration Tests - MEDIUM PRIORITY

- **Database Interaction**: Verify data persistence in SQLite.
- **PDF Generation**: existing `test_pdf_quality.py` integration.

## Implementation Steps

1. **Setup**: Create `tests/run_tests.py` and directory structure.
2. **Model Tests**: Create `tests/unit/test_data_manager.py`.
3. **Panel Tests**: Create `tests/unit/test_panels.py` (requires QApplication instance logic).
4. **Execution**: Run tests and fix discovered bugs.

## Dependencies

- `PySide6` (for UI tests)
- Standard libraries (`unittest`, `sqlite3`, `os`, `sys`)
