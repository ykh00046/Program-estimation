"""배합 레시피 편집 다이얼로그 (PDCA #37 recipe_ssot_unification).

배합(Mixing) 레시피의 추가/수정/비활성화 + Excel 명시적 재가져오기.
표현/입력만 담당하고 영속화는 DataManager(SSOT=recipes 테이블)에 위임한다.
(DHR 레시피는 별도 화면 `recipe_management_interface` — 본 다이얼로그와 무관)
"""
from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QSplitter, QWidget,
)

from utils.logger import logger
from ui.styles import UIStyles, UITheme

_COL_CODE = 0
_COL_NAME = 1
_COL_RATIO = 2

# 비율 합 100% 판정 허용 오차
_RATIO_SUM_TOLERANCE = 0.01


class RecipeEditDialog(QDialog):
    """배합 레시피 편집 다이얼로그."""

    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.setWindowTitle("배합 레시피 편집")
        self.setMinimumSize(760, 520)
        try:
            self.setStyleSheet(UIStyles.get_dialog_style())
        except Exception:  # noqa: BLE001 — 스타일 누락 시 기본 스타일로 표시
            pass
        self._init_ui()
        self._reload_list()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_list_panel())
        splitter.addWidget(self._build_form_panel())
        splitter.setSizes([220, 540])
        layout.addWidget(splitter, stretch=1)
        layout.addLayout(self._build_bottom_row())

    def _build_list_panel(self) -> QWidget:
        panel = QWidget()
        box = QVBoxLayout(panel)
        box.setContentsMargins(0, 0, 8, 0)
        box.setSpacing(8)

        title = QLabel("레시피 목록")
        title.setStyleSheet(f"color: {UITheme.TEXT_PRIMARY}; font-weight: 600;")
        box.addWidget(title)

        self.recipe_list = QListWidget()
        self.recipe_list.currentTextChanged.connect(self._on_recipe_selected)
        box.addWidget(self.recipe_list)

        self.new_btn = QPushButton("새 레시피")
        self.new_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        self.new_btn.clicked.connect(self._on_new_recipe)
        box.addWidget(self.new_btn)
        return panel

    def _build_form_panel(self) -> QWidget:
        panel = QWidget()
        box = QVBoxLayout(panel)
        box.setContentsMargins(8, 0, 0, 0)
        box.setSpacing(8)

        name_row = QHBoxLayout()
        name_label = QLabel("레시피명:")
        name_label.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY};")
        name_row.addWidget(name_label)
        self.name_edit = QLineEdit()
        name_row.addWidget(self.name_edit, 1)
        box.addLayout(name_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["품목코드", "품목명", "배합비율(%)"])
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(UIStyles.get_table_style())
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(_COL_NAME, QHeaderView.Stretch)
        header.setSectionResizeMode(_COL_CODE, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(_COL_RATIO, QHeaderView.ResizeToContents)
        self.table.itemChanged.connect(self._update_ratio_sum)
        box.addWidget(self.table, stretch=1)

        row_btns = QHBoxLayout()
        self.add_row_btn = QPushButton("행 추가")
        self.add_row_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        self.add_row_btn.clicked.connect(self._add_row)
        row_btns.addWidget(self.add_row_btn)
        self.remove_row_btn = QPushButton("행 삭제")
        self.remove_row_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        self.remove_row_btn.clicked.connect(self._remove_row)
        row_btns.addWidget(self.remove_row_btn)
        row_btns.addStretch(1)
        self.ratio_sum_label = QLabel("비율 합: 0%")
        row_btns.addWidget(self.ratio_sum_label)
        box.addLayout(row_btns)
        return panel

    def _build_bottom_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self.import_btn = QPushButton("Excel에서 가져오기")
        self.import_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        self.import_btn.clicked.connect(self._on_import_excel)
        row.addWidget(self.import_btn)

        self.delete_btn = QPushButton("레시피 삭제")
        self.delete_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        self.delete_btn.clicked.connect(self._on_delete)
        row.addWidget(self.delete_btn)

        row.addStretch(1)

        self.save_btn = QPushButton("저장")
        self.save_btn.setStyleSheet(UIStyles.get_primary_button_style())
        self.save_btn.clicked.connect(self._on_save)
        row.addWidget(self.save_btn)

        close_btn = QPushButton("닫기")
        close_btn.setStyleSheet(UIStyles.get_secondary_button_style())
        close_btn.clicked.connect(self.accept)
        row.addWidget(close_btn)
        return row

    # ------------------------------------------------------------------
    # 목록 / 폼
    # ------------------------------------------------------------------

    def _reload_list(self, select: str = "") -> None:
        """DataManager 재로드 후 목록 갱신."""
        try:
            self.data_manager.load_recipes()
            names = self.data_manager.get_recipe_names()
        except Exception as e:  # noqa: BLE001 — 다이얼로그 안정성 우선
            logger.error(f"레시피 목록 로드 실패: {e}", exc_info=True)
            names = []
        self.recipe_list.blockSignals(True)
        self.recipe_list.clear()
        self.recipe_list.addItems(names)
        self.recipe_list.blockSignals(False)
        if select and select in names:
            self.recipe_list.setCurrentRow(names.index(select))

    def _on_recipe_selected(self, name: str) -> None:
        if not name:
            return
        self.name_edit.setText(name)
        items = self.data_manager.get_recipe_items(name)
        self._fill_table(items)

    def _on_new_recipe(self) -> None:
        self.recipe_list.clearSelection()
        self.name_edit.clear()
        self._fill_table([])
        self.name_edit.setFocus()

    def _fill_table(self, items: List[Dict]) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(items))
        for r, m in enumerate(items):
            self.table.setItem(r, _COL_CODE, QTableWidgetItem(str(m.get("품목코드", ""))))
            self.table.setItem(r, _COL_NAME, QTableWidgetItem(str(m.get("품목명", ""))))
            self.table.setItem(r, _COL_RATIO,
                               QTableWidgetItem(f"{float(m.get('배합비율', 0.0)):g}"))
        self.table.blockSignals(False)
        self._update_ratio_sum()

    def _add_row(self) -> None:
        self.table.insertRow(self.table.rowCount())

    def _remove_row(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            row = self.table.rowCount() - 1
        if row >= 0:
            self.table.removeRow(row)
        self._update_ratio_sum()

    # ------------------------------------------------------------------
    # 데이터 수집 / 검증
    # ------------------------------------------------------------------

    def _cell_text(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text().strip() if item is not None else ""

    def _collect_materials(self) -> List[Dict]:
        """테이블에서 자재 목록 수집 (빈 행 스킵). 비율 비숫자는 ValueError."""
        materials: List[Dict] = []
        for r in range(self.table.rowCount()):
            code = self._cell_text(r, _COL_CODE)
            name = self._cell_text(r, _COL_NAME)
            ratio_text = self._cell_text(r, _COL_RATIO)
            if not code and not name and not ratio_text:
                continue
            try:
                ratio = float(ratio_text)
            except (TypeError, ValueError):
                raise ValueError(f"{r + 1}행: 배합비율이 숫자가 아닙니다 ('{ratio_text}')")
            if ratio <= 0:
                raise ValueError(f"{r + 1}행: 배합비율은 0보다 커야 합니다")
            materials.append({
                "품목코드": code or name,
                "품목명": name or code,
                "배합비율": ratio,
            })
        return materials

    def _ratio_sum(self) -> float:
        total = 0.0
        for r in range(self.table.rowCount()):
            try:
                total += float(self._cell_text(r, _COL_RATIO) or 0.0)
            except (TypeError, ValueError):
                continue
        return total

    def _update_ratio_sum(self, *_args) -> None:
        total = self._ratio_sum()
        ok = abs(total - 100.0) <= _RATIO_SUM_TOLERANCE
        color = UITheme.TEXT_SECONDARY if ok else UITheme.WARNING_COLOR
        self.ratio_sum_label.setText(f"비율 합: {total:g}%")
        self.ratio_sum_label.setStyleSheet(f"color: {color}; font-weight: 600;")

    # ------------------------------------------------------------------
    # 액션 (영속화는 DataManager 위임)
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "입력 오류", "레시피명을 입력하세요.")
            return
        try:
            materials = self._collect_materials()
        except ValueError as e:
            QMessageBox.warning(self, "입력 오류", str(e))
            return
        if not materials:
            QMessageBox.warning(self, "입력 오류", "자재를 1개 이상 입력하세요.")
            return

        total = self._ratio_sum()
        if abs(total - 100.0) > _RATIO_SUM_TOLERANCE:
            reply = QMessageBox.question(
                self, "비율 확인",
                f"배합비율 합이 {total:g}%입니다 (100%가 아님).\n그대로 저장하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return

        try:
            self.data_manager.save_recipe(name, materials)
        except Exception as e:  # noqa: BLE001
            logger.error(f"레시피 저장 실패: {e}", exc_info=True)
            QMessageBox.warning(self, "저장 실패", "레시피 저장 중 오류가 발생했습니다.")
            return
        QMessageBox.information(self, "저장 완료",
                                f"레시피 '{name}'이(가) 저장되었습니다. ({len(materials)}개 자재)")
        self._reload_list(select=name)

    def _on_delete(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "선택 없음", "삭제할 레시피를 선택하세요.")
            return
        reply = QMessageBox.question(
            self, "레시피 삭제",
            f"레시피 '{name}'을(를) 삭제하시겠습니까?\n"
            "(기존 배합 기록은 영향받지 않으며, 목록에서만 제거됩니다)",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        if self.data_manager.deactivate_recipe(name):
            QMessageBox.information(self, "삭제 완료", f"레시피 '{name}'이(가) 삭제되었습니다.")
            self._on_new_recipe()
            self._reload_list()
        else:
            QMessageBox.warning(self, "삭제 실패", f"레시피 '{name}'을(를) 찾을 수 없습니다.")

    def _on_import_excel(self) -> None:
        reply = QMessageBox.question(
            self, "Excel에서 가져오기",
            "레시피.xlsx의 레시피를 가져옵니다.\n"
            "같은 이름의 레시피는 Excel 내용으로 덮어쓰입니다.\n진행하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            imported = self.data_manager.seed_recipes_from_excel()
        except Exception as e:  # noqa: BLE001
            logger.error(f"Excel 레시피 가져오기 실패: {e}", exc_info=True)
            QMessageBox.warning(self, "가져오기 실패", "Excel 가져오기 중 오류가 발생했습니다.")
            return
        QMessageBox.information(self, "가져오기 완료", f"{imported}종의 레시피를 가져왔습니다.")
        self._reload_list()
