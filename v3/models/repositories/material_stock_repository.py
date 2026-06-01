"""자재 재고(`material_stock`) 도메인 Repository (PDCA #28).

`MixingDatabaseManager`(Facade)에서 자재 재고 조회/upsert/시드 책임을 분리한 것.
원본 기능: PDCA `material-stock-threshold-alert`.
SQL·로그·반환 구조는 분리 이전과 비트-동일하게 유지된다(무동작 변경 리팩토링).
"""
from typing import Dict, List

from utils.logger import logger
from utils.error_handler import handle_exceptions
from models._sqlite_base import SqliteManagerBase


class MaterialStockRepository(SqliteManagerBase):
    """`material_stock` 테이블 전용 Repository."""

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
                updated += cursor.rowcount or 0
            conn.commit()
        logger.debug(f"재고 자동 차감: {updated}건 갱신 (요청 {len(totals)}종)")
        return updated

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


__all__ = ["MaterialStockRepository"]
