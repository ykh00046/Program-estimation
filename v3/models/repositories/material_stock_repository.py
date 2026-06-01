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
                              unit: str = "g") -> bool:
        """material_code 기준 INSERT 또는 UPDATE."""
        code = (material_code or material_name or "").strip()
        if not code:
            logger.warning("자재 재고 upsert 실패: material_code/이름이 비어 있음")
            return False
        current = max(0.0, float(current_stock or 0.0))
        threshold = max(0.0, float(min_stock_threshold or 0.0))
        with self.get_connection() as conn:
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
            conn.commit()
        return True

    @handle_exceptions(user_message="자재 재고 차감 중 오류가 발생했습니다.", default_return=0)
    def apply_consumption(self, consumption: List[Dict]) -> int:
        """배합 사용량만큼 기존 재고를 차감한다(현재고는 0 미만으로 내려가지 않음).

        Args:
            consumption: ``[{"material_code": str, "actual_amount": float}, ...]``

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
                        conn, code, name, MOVE_CONSUME, -amount, stock_after, unit, "배합 자동 차감"
                    )
            conn.commit()
        logger.debug(f"재고 자동 차감: {updated}건 갱신 (요청 {len(totals)}종)")
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
                [code, name, qty, unit],
            )
            after = conn.execute(
                "SELECT current_stock FROM material_stock WHERE material_code = ?", [code]
            ).fetchone()
            stock_after = float(after["current_stock"]) if after else qty
            self._insert_history(conn, code, name, MOVE_INBOUND, qty, stock_after, unit, note or "")
            conn.commit()
        logger.info(f"입고 등록: {code} +{qty}{unit} → 재고 {stock_after}{unit}")
        return True

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


__all__ = ["MaterialStockRepository", "MOVE_INBOUND", "MOVE_CONSUME", "MOVE_ADJUST"]
