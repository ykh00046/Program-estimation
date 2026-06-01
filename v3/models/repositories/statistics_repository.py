"""통계 집계 도메인 Repository (PDCA #28).

`MixingDatabaseManager`(Facade)에서 통계/집계 조회 책임을 분리한 것.
`mixing_records` / `mixing_details` / `recipes`를 조인·집계해 읽기 전용으로 사용한다.
SQL·로그·반환 구조는 분리 이전과 비트-동일하게 유지된다(무동작 변경 리팩토링).
"""
from typing import Dict, List, Optional

from utils.logger import logger
from utils.error_handler import handle_exceptions
from models._sqlite_base import SqliteManagerBase


class StatisticsRepository(SqliteManagerBase):
    """배합/레시피 통계 집계 전용 Repository (읽기 전용)."""

    def get_statistics(self) -> Dict:
        """간단한 통계 정보를 반환합니다."""
        with self.get_connection() as conn:
            stats = {}

            # 총 배합 건수
            cursor = conn.execute("SELECT COUNT(*) as total_records FROM mixing_records")
            stats['total_records'] = cursor.fetchone()['total_records']

            # 최근 7일 배합 건수
            cursor = conn.execute("""
                SELECT COUNT(*) as recent_records
                FROM mixing_records
                WHERE work_date >= date('now', '-7 days')
            """)
            stats['recent_records'] = cursor.fetchone()['recent_records']

            # 활성 레시피 수
            cursor = conn.execute("SELECT COUNT(DISTINCT recipe_name) as recipe_count FROM recipes WHERE is_active = 1")
            stats['recipe_count'] = cursor.fetchone()['recipe_count']

            return stats

    @handle_exceptions(user_message="품목별 배합량 집계 중 오류가 발생했습니다.", default_return=0.0)
    def sum_item_amount_by_date_range(self, start_date: str, end_date: str, material_name: str) -> float:
        """
        특정 기간 동안의 특정 품목의 총 실제 배합량을 계산합니다.

        Args:
            start_date: 시작 날짜 (YYYY-MM-DD)
            end_date: 종료 날짜 (YYYY-MM-DD)
            material_name: 품목명

        Returns:
            총 실제 배합량
        """
        with self.get_connection() as conn:
            query = """
                SELECT SUM(d.actual_amount) as total
                FROM mixing_details d
                JOIN mixing_records r ON d.mixing_record_id = r.id
                WHERE r.work_date BETWEEN ? AND ?
                AND d.material_name = ?;
            """
            cursor = conn.execute(query, (start_date, end_date, material_name))
            result = cursor.fetchone()

            total = result['total'] if result and result['total'] is not None else 0.0
            logger.debug(f"'{material_name}'의 총 배합량 집계 ({start_date}~{end_date}): {total}")
            return total

    # ------------------------------------------------------------------
    # Dashboard 집계 쿼리 (PDCA #17)
    # ------------------------------------------------------------------

    @handle_exceptions(user_message="월별 생산 통계 조회 중 오류가 발생했습니다.", default_return=[])
    def get_monthly_production_stats(self, months: int = 6) -> List[Dict]:
        """최근 N개월 월별 생산 통계 (오래된 순)."""
        if months <= 0:
            return []
        modifier = "-{0} months".format(months)
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT strftime('%Y-%m', work_date) AS year_month,
                       COUNT(*) AS record_count,
                       COALESCE(SUM(total_amount), 0) AS total_amount
                FROM mixing_records
                WHERE work_date >= date('now', ?)
                GROUP BY year_month
                ORDER BY year_month ASC
                """,
                (modifier,),
            )
            rows = [dict(row) for row in cursor.fetchall() if row["year_month"]]
            logger.debug(f"월별 생산 통계 조회: {len(rows)}개월")
            return rows

    @handle_exceptions(user_message="자재 사용량 집계 중 오류가 발생했습니다.", default_return=[])
    def get_top_materials(
        self,
        limit: int = 10,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict]:
        """기간 내 자재 사용량 TOP-N."""
        query = (
            "SELECT d.material_code, d.material_name, "
            "       SUM(d.actual_amount) AS total_actual, "
            "       COUNT(DISTINCT d.mixing_record_id) AS use_count "
            "FROM mixing_details d "
            "JOIN mixing_records r ON d.mixing_record_id = r.id "
            "WHERE 1=1"
        )
        params: List = []
        query = self._append_date_range(query, params, start_date, end_date, "r.work_date")
        query += " GROUP BY d.material_code, d.material_name ORDER BY total_actual DESC LIMIT ?"
        params.append(limit)
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = [dict(row) for row in cursor.fetchall()]
            logger.debug(f"자재 TOP-{limit} 조회: {len(rows)}건")
            return rows

    @handle_exceptions(user_message="작업자별 통계 조회 중 오류가 발생했습니다.", default_return=[])
    def get_worker_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict]:
        """기간 내 작업자별 통계 (건수 desc)."""
        query = (
            "SELECT worker, "
            "       COUNT(*) AS record_count, "
            "       COALESCE(SUM(total_amount), 0) AS total_amount, "
            "       COALESCE(AVG(total_amount), 0) AS avg_amount "
            "FROM mixing_records "
            "WHERE 1=1"
        )
        params: List = []
        query = self._append_date_range(query, params, start_date, end_date)
        query += " GROUP BY worker ORDER BY record_count DESC"
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = [dict(row) for row in cursor.fetchall()]
            logger.debug(f"작업자 통계 조회: {len(rows)}명")
            return rows

    @handle_exceptions(user_message="레시피 빈도 집계 중 오류가 발생했습니다.", default_return=[])
    def get_recipe_frequency(
        self,
        limit: int = 10,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict]:
        """기간 내 레시피 실행 빈도 TOP-N."""
        query = (
            "SELECT recipe_name, "
            "       COUNT(*) AS run_count, "
            "       COALESCE(SUM(total_amount), 0) AS total_amount "
            "FROM mixing_records "
            "WHERE 1=1"
        )
        params: List = []
        query = self._append_date_range(query, params, start_date, end_date)
        query += " GROUP BY recipe_name ORDER BY run_count DESC LIMIT ?"
        params.append(limit)
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = [dict(row) for row in cursor.fetchall()]
            logger.debug(f"레시피 빈도 TOP-{limit} 조회: {len(rows)}건")
            return rows


__all__ = ["StatisticsRepository"]
