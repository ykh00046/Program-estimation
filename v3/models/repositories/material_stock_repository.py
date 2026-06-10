"""자재 재고(`material_stock`) 도메인 Repository (PDCA #28).

`MixingDatabaseManager`(Facade)에서 자재 재고 조회/upsert/시드 책임을 분리한 것.
원본 기능: PDCA `material-stock-threshold-alert`.
SQL·로그·반환 구조는 분리 이전과 비트-동일하게 유지된다(무동작 변경 리팩토링).
"""
from typing import Dict, List, Optional

from utils.logger import logger
from utils.error_handler import handle_exceptions
from models._sqlite_base import SqliteManagerBase

# 재고 이동 유형 (material_stock_history.change_type) — PDCA #30
MOVE_INBOUND = "INBOUND"   # 입고/매입 (+)
MOVE_CONSUME = "CONSUME"   # 배합 자동 차감 (-)
MOVE_ADJUST = "ADJUST"     # 수동 조정 (예약, 현재 미사용)

# LOT 역추적 note 포맷 (PDCA #34) — 미차감 검출 LIKE 매칭의 단일 진실
LOT_NOTE_SUFFIX_FMT = "(LOT {lot})"
CONSUME_NOTE_FMT = "배합 자동 차감 (LOT {lot})"
RETRO_NOTE_FMT = "소급 차감 (LOT {lot})"
RECONCILE_NOTE = "정합성 보정(장부 정렬)"
MANUAL_EDIT_NOTE = "수동 편집"

# 장부 체인 비교 허용 오차 (부동소수 누적 대비)
LEDGER_TOLERANCE = 1e-6


class MaterialStockRepository(SqliteManagerBase):
    """`material_stock`(현재 상태) + `material_stock_history`(이동 로그) 전용 Repository."""

    @handle_exceptions(user_message="자재 재고 조회 중 오류가 발생했습니다.", default_return=[])
    def get_all_material_stock(self) -> List[Dict]:
        """material_stock 전체 조회 (자재명 오름차순)."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT material_code, material_name, current_stock, "
                "       min_stock_threshold, unit, updated_at "
                "FROM material_stock ORDER BY material_name ASC"
            )
            rows = [dict(row) for row in cursor.fetchall()]
            logger.debug(f"자재 재고 전체 조회: {len(rows)}건")
            return rows

    @handle_exceptions(user_message="저재고 자재 조회 중 오류가 발생했습니다.", default_return=[])
    def get_low_stock_materials(self, default_threshold: float = 0.0) -> List[Dict]:
        """현재고가 유효 임계값 이하인 자재 목록.

        유효 임계값 = min_stock_threshold>0 이면 그 값, 아니면 default_threshold.
        유효 임계값이 0 이하인 자재는 알림 대상에서 제외한다.
        반환 dict: material_code, material_name, current_stock, threshold,
                  shortage(=threshold-current_stock), unit
        """
        default = float(default_threshold or 0.0)
        query = (
            "SELECT material_code, material_name, current_stock, unit, "
            "       CASE WHEN min_stock_threshold > 0 THEN min_stock_threshold ELSE ? END AS threshold "
            "FROM material_stock "
            "WHERE (CASE WHEN min_stock_threshold > 0 THEN min_stock_threshold ELSE ? END) > 0 "
            "  AND current_stock <= (CASE WHEN min_stock_threshold > 0 THEN min_stock_threshold ELSE ? END)"
        )
        with self.get_connection() as conn:
            cursor = conn.execute(query, [default, default, default])
            rows = [dict(row) for row in cursor.fetchall()]
        for row in rows:
            threshold = float(row.get("threshold") or 0.0)
            current = float(row.get("current_stock") or 0.0)
            row["shortage"] = round(threshold - current, 6)
        rows.sort(key=lambda r: r.get("shortage", 0.0), reverse=True)
        logger.debug(f"저재고 자재 조회: {len(rows)}건 (기본임계값={default})")
        return rows

    @handle_exceptions(user_message="자재 재고 저장 중 오류가 발생했습니다.", default_return=False)
    def upsert_material_stock(self, material_code: str, material_name: str,
                              current_stock: float, min_stock_threshold: float,
                              unit: str = "g", log_history: bool = False) -> bool:
        """material_code 기준 INSERT 또는 UPDATE.

        log_history=True면 재고 변경분(delta≠0)을 ADJUST 이력으로 기록한다 (PDCA #34).
        수동 편집 진입점(재고 설정 다이얼로그 → DataManager)에서만 켠다 —
        기본 False로 기존 호출(시드/테스트 셋업)의 동작을 비트 보존한다.
        """
        code = (material_code or material_name or "").strip()
        if not code:
            logger.warning("자재 재고 upsert 실패: material_code/이름이 비어 있음")
            return False
        current = max(0.0, float(current_stock or 0.0))
        threshold = max(0.0, float(min_stock_threshold or 0.0))
        with self.get_connection() as conn:
            old = conn.execute(
                "SELECT current_stock FROM material_stock WHERE material_code = ?", [code]
            ).fetchone()
            old_stock = float(old["current_stock"]) if old else 0.0
            conn.execute(
                """
                INSERT INTO material_stock
                    (material_code, material_name, current_stock, min_stock_threshold, unit, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(material_code) DO UPDATE SET
                    material_name = excluded.material_name,
                    current_stock = excluded.current_stock,
                    min_stock_threshold = excluded.min_stock_threshold,
                    unit = excluded.unit,
                    updated_at = CURRENT_TIMESTAMP
                """,
                [code, (material_name or code), current, threshold, (unit or "g")],
            )
            # 수동 편집도 감사 추적 (PDCA #34) — 변경분(delta≠0)만 ADJUST 이력 기록.
            # 설정 다이얼로그의 무변경 일괄 저장은 이력을 만들지 않는다.
            delta = current - old_stock
            if log_history and abs(delta) > LEDGER_TOLERANCE:
                self._insert_history(conn, code, (material_name or code), MOVE_ADJUST,
                                     delta, current, (unit or "g"), MANUAL_EDIT_NOTE)
            conn.commit()
        return True

    @handle_exceptions(user_message="자재 재고 차감 중 오류가 발생했습니다.", default_return=0)
    def apply_consumption(self, consumption: List[Dict], note: str = "배합 자동 차감") -> int:
        """배합 사용량만큼 기존 재고를 차감한다(현재고는 0 미만으로 내려가지 않음).

        Args:
            consumption: ``[{"material_code": str, "actual_amount": float}, ...]``
            note: CONSUME 이력 메모. LOT 역추적을 위해 ``CONSUME_NOTE_FMT`` 사용 권장
                  (PDCA #34). 기본값은 기존 문자열(하위 호환).

        동작:
            - material_code 기준으로 사용량을 합산한다.
            - 비양수 사용량·빈 코드는 건너뛴다.
            - 단일 트랜잭션에서 기존 행만 ``current_stock = max(0, current_stock - amt)``
              로 UPDATE 한다. 마스터에 없는 자재는 생성하지 않는다(UPDATE rowcount 0).

        Returns:
            실제 차감(갱신)된 자재 수.
        """
        totals: Dict[str, float] = {}
        for item in consumption or []:
            code = str(item.get("material_code") or "").strip()
            try:
                amount = float(item.get("actual_amount") or 0.0)
            except (TypeError, ValueError):
                amount = 0.0
            if not code or amount <= 0:
                continue
            totals[code] = totals.get(code, 0.0) + amount
        if not totals:
            return 0
        updated = 0
        with self.get_connection() as conn:
            for code, amount in totals.items():
                cursor = conn.execute(
                    "UPDATE material_stock "
                    "SET current_stock = MAX(0, current_stock - ?), updated_at = CURRENT_TIMESTAMP "
                    "WHERE material_code = ?",
                    [amount, code],
                )
                if cursor.rowcount:
                    updated += cursor.rowcount
                    # 차감과 동일 트랜잭션에서 CONSUME 이력 기록 (PDCA #30, 부호 -)
                    after = conn.execute(
                        "SELECT current_stock, material_name, unit FROM material_stock WHERE material_code = ?",
                        [code],
                    ).fetchone()
                    stock_after = float(after["current_stock"]) if after else 0.0
                    name = after["material_name"] if after else code
                    unit = after["unit"] if after else "g"
                    self._insert_history(
                        conn, code, name, MOVE_CONSUME, -amount, stock_after, unit, note
                    )
            conn.commit()
        logger.debug(f"재고 자동 차감: {updated}건 갱신 (요청 {len(totals)}종)")
        return updated

    @handle_exceptions(user_message="자재 재고 조정 중 오류가 발생했습니다.", default_return=0)
    def apply_adjustment(self, items: List[Dict], note: str = "재고 조정") -> int:
        """부호 있는 델타(``delta``)를 기존 재고에 적용하고 MOVE_ADJUST 이력을 기록한다.

        배합 기록 수정/삭제에 따른 재고 원복(+)·재정산(-)에 사용한다(PDCA #31).
        ``apply_consumption``(차감 전용, CONSUME)과 달리 양/음 델타를 모두 처리한다.

        Args:
            items: ``[{"material_code": str, "delta": float}, ...]``
                   delta > 0 = 가산(원복), delta < 0 = 차감(재정산). 0/빈코드는 건너뜀.
            note:  이력 메모(예: "배합 기록 삭제 원복", "배합 수정 재차감").

        동작:
            - material_code 기준으로 델타를 합산한다.
            - 단일 트랜잭션에서 기존 행만 ``current_stock = MAX(0, current_stock + delta)``
              로 UPDATE 한다. 마스터에 없는 자재는 생성하지 않는다(rowcount 0 → 이력 미기록).
            - UPDATE 성공한 자재마다 동일 트랜잭션에서 MOVE_ADJUST 이력(부호 있는 delta)을 기록.

        Returns:
            실제 조정(갱신)된 자재 수.
        """
        totals: Dict[str, float] = {}
        for item in items or []:
            code = str(item.get("material_code") or "").strip()
            try:
                delta = float(item.get("delta") or 0.0)
            except (TypeError, ValueError):
                delta = 0.0
            if not code or delta == 0:
                continue
            totals[code] = totals.get(code, 0.0) + delta
        if not totals:
            return 0
        updated = 0
        with self.get_connection() as conn:
            for code, delta in totals.items():
                cursor = conn.execute(
                    "UPDATE material_stock "
                    "SET current_stock = MAX(0, current_stock + ?), updated_at = CURRENT_TIMESTAMP "
                    "WHERE material_code = ?",
                    [delta, code],
                )
                if cursor.rowcount:
                    updated += cursor.rowcount
                    # 조정과 동일 트랜잭션에서 ADJUST 이력 기록 (부호 있는 델타, PDCA #31)
                    after = conn.execute(
                        "SELECT current_stock, material_name, unit FROM material_stock WHERE material_code = ?",
                        [code],
                    ).fetchone()
                    stock_after = float(after["current_stock"]) if after else 0.0
                    name = after["material_name"] if after else code
                    unit = after["unit"] if after else "g"
                    self._insert_history(
                        conn, code, name, MOVE_ADJUST, delta, stock_after, unit, note
                    )
            conn.commit()
        logger.debug(f"재고 조정: {updated}건 갱신 (요청 {len(totals)}종, note={note})")
        return updated

    # ------------------------------------------------------------------
    # 입고 / 이동 이력 (PDCA #30 inventory_inbound_history)
    # ------------------------------------------------------------------

    @handle_exceptions(user_message="입고 등록 중 오류가 발생했습니다.", default_return=False)
    def add_inbound(self, material_code: str, material_name: str, quantity: float,
                    unit: str = "g", note: str = "") -> bool:
        """입고(매입): 기존 재고에 ``quantity``를 더한다(마스터에 없으면 신규 생성).

        ``upsert_material_stock``(절대값 설정)과 달리 **누적 가산**한다.
        이동 이력(INBOUND, +quantity, stock_after)을 동일 트랜잭션에 기록한다.
        Returns: 성공 시 True, 코드 공백/비양수 수량이면 False.
        """
        code = (material_code or material_name or "").strip()
        if not code:
            logger.warning("입고 등록 실패: material_code/이름이 비어 있음")
            return False
        try:
            qty = float(quantity or 0.0)
        except (TypeError, ValueError):
            qty = 0.0
        if qty <= 0:
            logger.warning(f"입고 등록 실패: 수량이 비양수임 (code={code}, qty={qty})")
            return False
        name = (material_name or code)
        unit = (unit or "g")
        with self.get_connection() as conn:
            stock_after = self._apply_inbound(conn, code, name, qty, unit, note or "")
            conn.commit()
        logger.info(f"입고 등록: {code} +{qty}{unit} → 재고 {stock_after}{unit}")
        return True

    def apply_replenishment(self, material_code: str, material_name: str, quantity: float,
                            unit: str = "g", note: str = "") -> bool:
        """재고 보충(입고)의 공개 별칭 (PDCA #32 R3).

        ``add_inbound``과 완전히 동일하게 누적 가산 + INBOUND 이력을 기록한다.
        사용자 요청 명칭(apply_replenishment)으로도 호출 가능하도록 제공한다.
        """
        return self.add_inbound(material_code, material_name, quantity, unit, note)

    def _apply_inbound(self, conn, material_code: str, material_name: str, quantity: float,
                       unit: str, note: str) -> float:
        """주어진 conn(트랜잭션) 안에서 재고 누적 가산 + INBOUND 이력 기록.

        커밋은 호출자 책임. 발주 입고(PurchaseOrderRepository)와 단발 입고(add_inbound)가
        공유하는 입고 반영 코어. 사전조건: material_code 비어있지 않음, quantity > 0.
        Returns: 이동 후 재고(stock_after).
        """
        name = (material_name or material_code)
        unit = (unit or "g")
        conn.execute(
            """
            INSERT INTO material_stock
                (material_code, material_name, current_stock, min_stock_threshold, unit, updated_at)
            VALUES (?, ?, ?, 0, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(material_code) DO UPDATE SET
                material_name = excluded.material_name,
                current_stock = current_stock + excluded.current_stock,
                unit = excluded.unit,
                updated_at = CURRENT_TIMESTAMP
            """,
            [material_code, name, float(quantity), unit],
        )
        after = conn.execute(
            "SELECT current_stock FROM material_stock WHERE material_code = ?", [material_code]
        ).fetchone()
        stock_after = float(after["current_stock"]) if after else float(quantity)
        self._insert_history(conn, material_code, name, MOVE_INBOUND, float(quantity),
                             stock_after, unit, note or "")
        return stock_after

    @handle_exceptions(user_message="입출고 이력 조회 중 오류가 발생했습니다.", default_return=[])
    def get_stock_history(self, material_code: Optional[str] = None, limit: int = 200) -> List[Dict]:
        """재고 이동 이력을 최신순으로 조회한다. ``material_code`` 지정 시 해당 자재만."""
        query = (
            "SELECT material_code, material_name, change_type, quantity, "
            "       stock_after, unit, note, created_at "
            "FROM material_stock_history "
        )
        params: List = []
        code = (material_code or "").strip()
        if code:
            query += "WHERE material_code = ? "
            params.append(code)
        query += "ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(int(limit) if limit else 200)
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = [dict(row) for row in cursor.fetchall()]
        logger.debug(f"입출고 이력 조회: {len(rows)}건 (자재={code or '전체'})")
        return rows

    # ------------------------------------------------------------------
    # 정합성 검사 / 보정 (PDCA #34 inventory_reconcile)
    # ------------------------------------------------------------------

    _LEDGER_QUERY = (
        "SELECT s.material_code, s.material_name, s.current_stock, s.unit, "
        "       (SELECT h.stock_after FROM material_stock_history h "
        "        WHERE h.material_code = s.material_code "
        "        ORDER BY h.created_at DESC, h.id DESC LIMIT 1) AS ledger_stock "
        "FROM material_stock s ORDER BY s.material_name ASC"
    )

    @handle_exceptions(user_message="재고 정합성 검사 중 오류가 발생했습니다.", default_return=[])
    def check_ledger_consistency(self, tolerance: float = LEDGER_TOLERANCE) -> List[Dict]:
        """현재고와 장부(최근 이력 stock_after)의 불일치 자재를 반환한다.

        불변식: current_stock == 최근 history.stock_after (이력 없으면 0).
        clamp(MAX 0) 때문에 Σquantity replay는 부정확하므로 stock_after 체인을 기준으로 한다.

        Returns: ``[{material_code, material_name, current_stock, ledger_stock, drift, unit}]``
                 (drift = current_stock - ledger_stock, |drift| > tolerance인 자재만)
        """
        issues: List[Dict] = []
        with self.get_connection() as conn:
            for row in conn.execute(self._LEDGER_QUERY).fetchall():
                current = float(row["current_stock"] or 0.0)
                ledger = float(row["ledger_stock"]) if row["ledger_stock"] is not None else 0.0
                drift = current - ledger
                if abs(drift) > tolerance:
                    issues.append({
                        "material_code": row["material_code"],
                        "material_name": row["material_name"],
                        "current_stock": current,
                        "ledger_stock": ledger,
                        "drift": round(drift, 6),
                        "unit": row["unit"] or "g",
                    })
        logger.debug(f"재고 정합성 검사: 불일치 {len(issues)}건")
        return issues

    @handle_exceptions(user_message="장부 정렬 중 오류가 발생했습니다.", default_return=False)
    def record_reconcile_entry(self, material_code: str, note: str = RECONCILE_NOTE) -> bool:
        """장부 체인을 현재고에 정렬하는 ADJUST 이력 1건을 기록한다 (재고는 불변).

        현재고가 사용자가 보는 진실이므로 재고를 바꾸지 않고 이력만 추가해
        '현재고 == 최근 stock_after' 불변식을 복구한다 (PDCA #34 설계 결정 2).
        Returns: 이력 기록 시 True, drift가 허용 오차 이내면 False.
        """
        code = (material_code or "").strip()
        if not code:
            return False
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT material_name, current_stock, unit FROM material_stock "
                "WHERE material_code = ?", [code]
            ).fetchone()
            if not row:
                logger.warning(f"장부 정렬 실패: 자재 없음 ({code})")
                return False
            current = float(row["current_stock"] or 0.0)
            last = conn.execute(
                "SELECT stock_after FROM material_stock_history WHERE material_code = ? "
                "ORDER BY created_at DESC, id DESC LIMIT 1", [code]
            ).fetchone()
            ledger = float(last["stock_after"]) if last else 0.0
            drift = current - ledger
            if abs(drift) <= LEDGER_TOLERANCE:
                return False
            self._insert_history(conn, code, row["material_name"], MOVE_ADJUST,
                                 drift, current, row["unit"] or "g", note)
            conn.commit()
        logger.info(f"장부 정렬: {code} drift {drift:+g} 이력 기록 (재고 불변)")
        return True

    @handle_exceptions(user_message="미차감 기록 검사 중 오류가 발생했습니다.", default_return=[])
    def find_undeducted_lots(self, start_date: str, end_date: str) -> List[Dict]:
        """기간 내 배합 기록 중 차감 마커가 이력에 없는 LOT 목록 (PDCA #34 검사 2).

        cross-domain *읽기 전용* 조회 — mixing_records는 진단 목적으로만 읽으며
        수정은 MixingRecordRepository 영역이다. CONSUME(자동)·ADJUST(소급) 어느 쪽이든
        note에 '(LOT {lot})' 마커가 있으면 차감된 것으로 간주한다(중복 적용 방지).
        """
        query = (
            "SELECT r.product_lot, r.recipe_name, r.work_date, r.total_amount "
            "FROM mixing_records r "
            "WHERE r.work_date >= ? AND r.work_date <= ? "
            "  AND NOT EXISTS ("
            "      SELECT 1 FROM material_stock_history h "
            "      WHERE h.note LIKE '%(LOT ' || r.product_lot || ')%') "
            "ORDER BY r.work_date DESC, r.product_lot DESC"
        )
        with self.get_connection() as conn:
            rows = [dict(row) for row in conn.execute(query, [start_date, end_date]).fetchall()]
        logger.debug(f"미차감 의심 LOT 검사: {len(rows)}건 ({start_date}~{end_date})")
        return rows

    @staticmethod
    def _insert_history(conn, material_code: str, material_name: str, change_type: str,
                        quantity: float, stock_after: float, unit: str, note: str) -> None:
        """이동 이력 1건 INSERT (커밋은 호출자 책임)."""
        conn.execute(
            "INSERT INTO material_stock_history "
            "(material_code, material_name, change_type, quantity, stock_after, unit, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [material_code, material_name or material_code, change_type,
             float(quantity), float(stock_after), unit or "g", note or ""],
        )

    @handle_exceptions(user_message="자재 재고 초기화 중 오류가 발생했습니다.", default_return=0)
    def seed_material_stock_from_history(self) -> int:
        """배합 이력(mixing_details)의 자재를 재고 마스터에 없으면 0/0으로 시드.

        반환: 신규 삽입 건수.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO material_stock
                    (material_code, material_name, current_stock, min_stock_threshold, unit)
                SELECT
                    COALESCE(NULLIF(TRIM(d.material_code), ''), d.material_name) AS code,
                    MIN(d.material_name) AS name,
                    0, 0, 'g'
                FROM mixing_details d
                WHERE COALESCE(NULLIF(TRIM(d.material_code), ''), d.material_name) IS NOT NULL
                  AND COALESCE(NULLIF(TRIM(d.material_code), ''), d.material_name) <> ''
                GROUP BY code
                """
            )
            inserted = cursor.rowcount if cursor.rowcount is not None else 0
            conn.commit()
        logger.debug(f"자재 재고 시드: {inserted}건 신규 삽입")
        return inserted


__all__ = [
    "MaterialStockRepository", "MOVE_INBOUND", "MOVE_CONSUME", "MOVE_ADJUST",
    "LOT_NOTE_SUFFIX_FMT", "CONSUME_NOTE_FMT", "RETRO_NOTE_FMT",
    "RECONCILE_NOTE", "MANUAL_EDIT_NOTE", "LEDGER_TOLERANCE",
]
