"""자재 발주(Purchase Order) 도메인 Repository (PDCA #32 purchase_order_management).

발주 라이프사이클(발주 → 부분/완료 입고 → 취소)을 관리한다. 발주는 단일 자재 라인이며,
입고 처리 시 `MaterialStockRepository._apply_inbound`를 **같은 트랜잭션**에서 호출해
재고 누적 가산 + INBOUND 이력 기록을 원자적으로 수행한다(PDCA #30 교훈 3).

`material_stock`/`material_stock_history`는 그대로 재사용하고, 발주 헤더만 별 테이블
(`purchase_orders`)로 둔다(PDCA #18/#28/#30 자산 재사용 원칙).
"""
from datetime import datetime
from typing import Dict, List, Optional

from utils.logger import logger
from utils.error_handler import handle_exceptions
from models._sqlite_base import SqliteManagerBase

# 발주 상태 (purchase_orders.status) — PDCA #32
PO_PENDING = "PENDING"      # 대기 (입고 0)
PO_PARTIAL = "PARTIAL"      # 부분입고 (0 < 입고 < 발주)
PO_RECEIVED = "RECEIVED"    # 입고완료 (입고 >= 발주)
PO_CANCELLED = "CANCELLED"  # 취소

_OPEN_STATUSES = (PO_PENDING, PO_PARTIAL)  # 입고/취소 가능 상태


class PurchaseOrderRepository(SqliteManagerBase):
    """`purchase_orders`(발주 헤더) 전용 Repository. 입고 연동을 위해 재고 Repo를 주입받는다."""

    def __init__(self, db_path: str, stock_repo) -> None:
        super().__init__(db_path, log_prefix="데이터베이스")
        self._stock = stock_repo

    # ------------------------------------------------------------------
    # 생성 / 조회
    # ------------------------------------------------------------------

    @handle_exceptions(user_message="발주 등록 중 오류가 발생했습니다.", default_return=None)
    def create_purchase_order(self, material_code: str, material_name: str, supplier: str,
                              ordered_qty: float, unit: str = "g",
                              note: str = "") -> Optional[int]:
        """발주를 생성한다(상태 PENDING). 코드 공백/발주량 비양수면 None.

        Returns: 성공 시 발주 행 id, 실패 시 None.
        """
        code = (material_code or material_name or "").strip()
        if not code:
            logger.warning("발주 등록 실패: material_code/이름이 비어 있음")
            return None
        try:
            qty = float(ordered_qty or 0.0)
        except (TypeError, ValueError):
            qty = 0.0
        if qty <= 0:
            logger.warning(f"발주 등록 실패: 발주량이 비양수임 (code={code}, qty={qty})")
            return None
        name = (material_name or code)
        unit = (unit or "g")
        supplier = (supplier or "").strip()
        with self.get_connection() as conn:
            po_number = self._next_po_number(conn)
            cursor = conn.execute(
                """
                INSERT INTO purchase_orders
                    (po_number, material_code, material_name, supplier,
                     ordered_qty, received_qty, unit, status, note)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
                """,
                [po_number, code, name, supplier, qty, unit, PO_PENDING, note or ""],
            )
            po_id = cursor.lastrowid
            conn.commit()
        logger.info(f"발주 등록: {po_number} {code} {qty}{unit} (매입처={supplier or '-'})")
        return po_id

    @handle_exceptions(user_message="발주 조회 중 오류가 발생했습니다.", default_return=[])
    def get_purchase_orders(self, status: Optional[str] = None,
                            limit: int = 200) -> List[Dict]:
        """발주 목록을 최신순으로 조회한다. ``status`` 지정 시 해당 상태만.

        각 dict에 ``remaining_qty``(= ordered_qty − received_qty, 음수면 0)를 덧붙인다.
        """
        query = (
            "SELECT id, po_number, material_code, material_name, supplier, "
            "       ordered_qty, received_qty, unit, status, note, created_at, updated_at "
            "FROM purchase_orders "
        )
        params: List = []
        st = (status or "").strip()
        if st:
            query += "WHERE status = ? "
            params.append(st)
        query += "ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(int(limit) if limit else 200)
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = [dict(row) for row in cursor.fetchall()]
        for row in rows:
            ordered = float(row.get("ordered_qty") or 0.0)
            received = float(row.get("received_qty") or 0.0)
            row["remaining_qty"] = round(max(0.0, ordered - received), 6)
        logger.debug(f"발주 조회: {len(rows)}건 (상태={st or '전체'})")
        return rows

    # ------------------------------------------------------------------
    # 입고 / 취소
    # ------------------------------------------------------------------

    @handle_exceptions(user_message="발주 입고 처리 중 오류가 발생했습니다.", default_return=False)
    def receive_purchase_order(self, po_id: int, received_qty: Optional[float] = None,
                               note: str = "") -> bool:
        """발주 입고 처리(부분/전체). ``received_qty=None``이면 잔량 전체를 입고한다.

        단일 트랜잭션에서:
          1) 발주 행 조회·검증(존재·OPEN 상태)
          2) ``received_qty`` 갱신 + 상태 재계산 UPDATE
          3) ``MaterialStockRepository._apply_inbound``로 재고 누적 + INBOUND 이력
        모두 같은 conn에서 수행 후 한 번 커밋 → 원자성 확보.

        RECEIVED/CANCELLED 발주, 또는 입고량이 비양수면 False.
        """
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT id, po_number, material_code, material_name, unit, "
                "       ordered_qty, received_qty, status "
                "FROM purchase_orders WHERE id = ?",
                [po_id],
            ).fetchone()
            if row is None:
                logger.warning(f"발주 입고 실패: id={po_id} 없음")
                return False
            if row["status"] not in _OPEN_STATUSES:
                logger.warning(f"발주 입고 실패: id={po_id} 상태={row['status']} (입고 불가)")
                return False

            ordered = float(row["ordered_qty"] or 0.0)
            already = float(row["received_qty"] or 0.0)
            remaining = max(0.0, ordered - already)
            try:
                qty = float(received_qty) if received_qty is not None else remaining
            except (TypeError, ValueError):
                qty = 0.0
            if qty <= 0:
                logger.warning(f"발주 입고 실패: id={po_id} 입고량 비양수({qty})")
                return False

            new_received = already + qty
            new_status = self._status_for(ordered, new_received)
            conn.execute(
                "UPDATE purchase_orders "
                "SET received_qty = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                [new_received, new_status, po_id],
            )
            code = str(row["material_code"])
            name = str(row["material_name"] or code)
            unit = str(row["unit"] or "g")
            inbound_note = note or f"발주 {row['po_number']} 입고"
            stock_after = self._stock._apply_inbound(conn, code, name, qty, unit, inbound_note)
            conn.commit()
        logger.info(
            f"발주 입고: {row['po_number']} +{qty}{unit} → 누적 {new_received}/{ordered} "
            f"({new_status}), 재고 {stock_after}{unit}"
        )
        return True

    @handle_exceptions(user_message="발주 취소 중 오류가 발생했습니다.", default_return=False)
    def cancel_purchase_order(self, po_id: int) -> bool:
        """PENDING/PARTIAL 발주를 CANCELLED 처리한다. 이미 입고된 재고는 원복하지 않는다.

        RECEIVED/CANCELLED 발주이거나 존재하지 않으면 False.
        """
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT po_number, status FROM purchase_orders WHERE id = ?", [po_id]
            ).fetchone()
            if row is None:
                logger.warning(f"발주 취소 실패: id={po_id} 없음")
                return False
            if row["status"] not in _OPEN_STATUSES:
                logger.warning(f"발주 취소 실패: id={po_id} 상태={row['status']} (취소 불가)")
                return False
            conn.execute(
                "UPDATE purchase_orders "
                "SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                [PO_CANCELLED, po_id],
            )
            conn.commit()
        logger.info(f"발주 취소: {row['po_number']} → CANCELLED")
        return True

    # ------------------------------------------------------------------
    # 헬퍼
    # ------------------------------------------------------------------

    @staticmethod
    def _status_for(ordered_qty: float, received_qty: float) -> str:
        """발주량/입고량 관계로 상태 결정(취소 제외)."""
        if received_qty <= 0:
            return PO_PENDING
        if received_qty < ordered_qty:
            return PO_PARTIAL
        return PO_RECEIVED

    @staticmethod
    def _next_po_number(conn) -> str:
        """당일 순번 발주번호 `PO-YYYYMMDD-NNN`을 같은 conn에서 채번한다."""
        day = datetime.now().strftime("%Y%m%d")
        prefix = f"PO-{day}-"
        cursor = conn.execute(
            "SELECT COUNT(*) AS c FROM purchase_orders WHERE po_number LIKE ?",
            [prefix + "%"],
        )
        count = int(cursor.fetchone()["c"]) + 1
        return f"{prefix}{count:03d}"


__all__ = [
    "PurchaseOrderRepository",
    "PO_PENDING", "PO_PARTIAL", "PO_RECEIVED", "PO_CANCELLED",
]
