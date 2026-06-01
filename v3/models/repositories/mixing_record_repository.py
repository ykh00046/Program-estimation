"""배합 기록(`mixing_records` / `mixing_details`) 도메인 Repository (PDCA #28).

`MixingDatabaseManager`(Facade)에서 배합 기록 저장/조회/수정/삭제 책임을 분리한 것.
SQL·로그·반환 구조는 분리 이전과 비트-동일하게 유지된다(무동작 변경 리팩토링).
"""
from datetime import datetime
from typing import Dict, List, Optional

from utils.logger import logger
from utils.error_handler import handle_exceptions
from models._sqlite_base import SqliteManagerBase
from models.lot_utils import next_lot


class MixingRecordRepository(SqliteManagerBase):
    """`mixing_records` + `mixing_details` 테이블 전용 Repository."""

    @handle_exceptions(user_message="배합 기록 저장 중 오류가 발생했습니다.")
    def save_mixing_record(self, record_data: Dict, details: List[Dict]) -> int:
        """
        배합 기록을 저장합니다.

        Args:
            record_data: 기본 배합 정보
            details: 상세 배합 정보 리스트

        Returns:
            저장된 레코드의 ID
        """
        with self.get_connection() as conn:
            record_data["product_lot"] = self._resolve_unique_product_lot(conn, record_data)
            record_id = self._insert_mixing_record_row(conn, record_data)
            self._insert_mixing_detail_rows(conn, record_id, details)
            conn.commit()
            self._log_record_saved(record_data, record_id)
        return record_id

    def _generate_product_lot_with_conn(self, conn, recipe_name: str, work_date: str) -> str:
        """동일 connection 안에서 다음 시퀀스의 제품 LOT을 생성한다."""
        target_date = datetime.strptime(work_date, "%Y-%m-%d")
        date_str = target_date.strftime("%y%m%d")
        base_lot = f"{recipe_name}{date_str}"
        cursor = conn.execute(
            "SELECT product_lot FROM mixing_records WHERE work_date = ? AND recipe_name = ?",
            (work_date, recipe_name),
        )
        return next_lot(base_lot, (row["product_lot"] for row in cursor.fetchall()))

    def _resolve_unique_product_lot(self, conn, record_data: Dict) -> str:
        """요청된 LOT이 비었거나 이미 존재하면 동일 트랜잭션 안에서 유일 LOT을 재생성한다."""
        requested_lot = str(record_data.get("product_lot", "")).strip()
        if requested_lot:
            cursor = conn.execute(
                "SELECT 1 FROM mixing_records WHERE product_lot = ? LIMIT 1",
                (requested_lot,),
            )
            if cursor.fetchone() is None:
                return requested_lot
            logger.warning(f"Duplicate mixing product_lot detected; regenerating ({requested_lot})")

        recipe_name = str(record_data.get("recipe_name", "")).strip()
        work_date = str(record_data.get("work_date", "")).strip()
        if not recipe_name or not work_date:
            raise ValueError("recipe_name and work_date are required to generate a unique product LOT")
        return self._generate_product_lot_with_conn(conn, recipe_name, work_date)

    def _insert_mixing_record_row(self, conn, record_data: Dict) -> int:
        """mixing_records 행 1건을 삽입하고 lastrowid를 반환한다."""
        cursor = conn.execute("""
            INSERT INTO mixing_records
            (product_lot, recipe_name, worker, work_date, work_time, total_amount, scale)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            record_data['product_lot'],
            record_data['recipe_name'],
            record_data['worker'],
            record_data['work_date'],
            record_data['work_time'],
            record_data['total_amount'],
            record_data['scale'],
        ))
        return cursor.lastrowid

    def _insert_mixing_detail_rows(self, conn, record_id: int, details: List[Dict]) -> None:
        """mixing_details 행 N건을 sequence_order와 함께 삽입한다."""
        for i, detail in enumerate(details):
            conn.execute("""
                INSERT INTO mixing_details
                (mixing_record_id, material_code, material_name, material_lot,
                 ratio, theory_amount, actual_amount, sequence_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record_id,
                detail['material_code'],
                detail['material_name'],
                detail['material_lot'],
                detail['ratio'],
                detail['theory_amount'],
                detail['actual_amount'],
                i + 1,
            ))

    def _log_record_saved(self, record_data: Dict, record_id: int) -> None:
        """저장 완료 이벤트를 운영 로그에 남긴다."""
        logger.log_mixing_operation(
            "기록저장",
            record_data['recipe_name'],
            record_data['worker'],
            product_lot=record_data['product_lot'],
            record_id=record_id,
        )

    @handle_exceptions(user_message="배합 기록 조회 중 오류가 발생했습니다.", default_return=[])
    def get_mixing_records(self,
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None,
                          worker: Optional[str] = None,
                          recipe_name: Optional[str] = None,
                          limit: int = 100) -> List[Dict]:
        """
        배합 기록을 조회합니다.

        Args:
            start_date: 시작 날짜 (YYYY-MM-DD)
            end_date: 종료 날짜 (YYYY-MM-DD)
            worker: 작업자명
            recipe_name: 레시피명
            limit: 최대 조회 건수

        Returns:
            배합 기록 리스트
        """
        with self.get_connection() as conn:
            query = "SELECT * FROM mixing_records WHERE 1=1"
            params = []

            query = self._append_date_range(query, params, start_date, end_date)

            if worker:
                query += " AND worker = ?"
                params.append(worker)

            if recipe_name:
                query += " AND recipe_name = ?"
                params.append(recipe_name)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            records = [dict(row) for row in cursor.fetchall()]

            logger.debug(f"배합 기록 조회: {len(records)}건")
            return records

    @handle_exceptions(user_message="배합 상세 정보 조회 중 오류가 발생했습니다.", default_return=[])
    def get_mixing_details(self, mixing_record_id: int) -> List[Dict]:
        """특정 배합 기록의 상세 정보를 조회합니다."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM mixing_details
                WHERE mixing_record_id = ?
                ORDER BY sequence_order
            """, (mixing_record_id,))

            details = [dict(row) for row in cursor.fetchall()]
            logger.debug(f"배합 상세 조회: 레코드ID {mixing_record_id}, {len(details)}건")
            return details

    @handle_exceptions(user_message="배합 기록 삭제 중 오류가 발생했습니다.")
    def delete_mixing_record(self, record_id: int) -> bool:
        """
        배합 기록을 삭제합니다.

        Args:
            record_id: 삭제할 레코드 ID

        Returns:
            삭제 성공 여부
        """
        with self.get_connection() as conn:
            # 먼저 해당 레코드가 존재하는지 확인
            cursor = conn.execute("SELECT product_lot FROM mixing_records WHERE id = ?", (record_id,))
            record = cursor.fetchone()

            if not record:
                logger.warning(f"삭제할 레코드를 찾을 수 없습니다: ID {record_id}")
                return False

            product_lot = record['product_lot']

            # 상세 정보 먼저 삭제
            conn.execute("DELETE FROM mixing_details WHERE mixing_record_id = ?", (record_id,))

            # 기본 레코드 삭제
            conn.execute("DELETE FROM mixing_records WHERE id = ?", (record_id,))

            conn.commit()
            logger.info(f"배합 기록 삭제 완료: ID {record_id}, LOT {product_lot}")
            return True

    @handle_exceptions(user_message="배합 기록 조회 중 오류가 발생했습니다.", default_return=None)
    def get_mixing_record_by_lot(self, product_lot: str) -> Optional[Dict]:
        """
        제품 LOT 번호로 배합 기록을 조회합니다.

        Args:
            product_lot: 제품 LOT 번호

        Returns:
            배합 기록 (없으면 None)
        """
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM mixing_records WHERE product_lot = ?", (product_lot,))
            record = cursor.fetchone()

            if record:
                return dict(record)
            return None

    @handle_exceptions(user_message="배합 기록 수정 중 오류가 발생했습니다.", default_return=False)
    def update_mixing_record(self, record_id: int, worker: str, total_amount: float) -> bool:
        """
        배합 기본 기록을 수정합니다.

        Args:
            record_id: 레코드 ID
            worker: 작업자 이름
            total_amount: 배합량

        Returns:
            수정 성공 여부
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                UPDATE mixing_records
                SET worker = ?, total_amount = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (worker, total_amount, record_id))

            conn.commit()

            if cursor.rowcount > 0:
                logger.info(f"배합 기록 수정 완료: ID {record_id}")
                return True
            return False

    @handle_exceptions(user_message="배합 상세 정보 수정 중 오류가 발생했습니다.")
    def update_mixing_detail(self, record_id: int, material_code: str,
                              material_lot: str, ratio: float,
                              theory_amount: float, actual_amount: float) -> bool:
        """
        배합 상세 정보를 수정합니다.

        Args:
            record_id: 배합 기록 ID
            material_code: 품목코드
            material_lot: 자재 LOT
            ratio: 배합비율
            theory_amount: 이론계량
            actual_amount: 실제배합

        Returns:
            수정 성공 여부
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                UPDATE mixing_details
                SET material_lot = ?, ratio = ?, theory_amount = ?, actual_amount = ?
                WHERE mixing_record_id = ? AND material_code = ?
            """, (material_lot, ratio, theory_amount, actual_amount, record_id, material_code))

            conn.commit()

            if cursor.rowcount > 0:
                logger.debug(f"배합 상세 수정 완료: record_id={record_id}, material_code={material_code}")
                return True
            return False

    @handle_exceptions(user_message="배합 기록 수정 중 오류가 발생했습니다.", default_return=False)
    def update_mixing_record_with_details(self, record_id: int, worker: str,
                                          total_amount: float, materials: List[Dict]) -> bool:
        """기본 기록과 상세 자재들을 단일 트랜잭션으로 수정한다.

        자재별 개별 커밋(N+1)을 제거하여 부분 실패 시 전체 롤백을 보장한다.
        """
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE mixing_records
                SET worker = ?, total_amount = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (worker, total_amount, record_id))
            for material in materials:
                conn.execute("""
                    UPDATE mixing_details
                    SET material_lot = ?, ratio = ?, theory_amount = ?, actual_amount = ?
                    WHERE mixing_record_id = ? AND material_code = ?
                """, (
                    material.get('material_lot', ''),
                    material.get('ratio', 0),
                    material.get('theory_amount', 0),
                    material.get('actual_amount', 0),
                    record_id,
                    material['material_code'],
                ))
            conn.commit()
            logger.info(f"배합 기록(상세 포함) 수정 완료: ID {record_id}, 자재 {len(materials)}건")
            return True

    @handle_exceptions(user_message="배합 기록 전체 조회 중 오류가 발생했습니다.", default_return=[])
    def get_all_records_with_details(self, limit: int = 10000) -> List[Dict]:
        """모든 배합 기록과 상세 정보를 JOIN으로 한 번에 조회합니다."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT r.id, r.product_lot, r.recipe_name, r.worker,
                       r.work_date, r.work_time, r.total_amount, r.scale,
                       r.created_at, r.updated_at,
                       d.material_code, d.material_name, d.material_lot,
                       d.ratio, d.theory_amount, d.actual_amount,
                       d.sequence_order
                FROM mixing_records r
                JOIN mixing_details d ON d.mixing_record_id = r.id
                ORDER BY r.created_at DESC, d.sequence_order
                LIMIT ?
            """, (limit,))
            results = [dict(row) for row in cursor.fetchall()]
            logger.debug(f"배합 기록+상세 일괄 조회: {len(results)}건")
            return results

    @handle_exceptions(user_message="전체 품목명 조회 중 오류가 발생했습니다.", default_return=[])
    def get_all_material_names(self) -> List[str]:
        """데이터베이스에 기록된 모든 고유 품목명을 조회합니다."""
        with self.get_connection() as conn:
            query = "SELECT DISTINCT material_name FROM mixing_details ORDER BY material_name;"
            cursor = conn.execute(query)
            names = [row['material_name'] for row in cursor.fetchall()]
            logger.debug(f"전체 고유 품목명 조회: {len(names)}건")
            return names


__all__ = ["MixingRecordRepository"]
