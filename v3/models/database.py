"""배합 기록(`mixing_records.db`) 전용 데이터베이스 매니저.

이 모듈은 일반 배합 작업의 `mixing_records` / `mixing_details` / `recipes` 테이블만 다룬다.
DHR(Device History Record) 데이터는 `models.dhr_database.DhrDatabaseManager`를 사용하라.

공통 인프라(`get_connection`, `_ensure_database_exists`)는 `models._sqlite_base.SqliteManagerBase`에 위치한다.
"""
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

from config.settings import DB_FILE, LEGACY_DB_PATH, USER_DATA_DIR
from utils.logger import logger
from utils.error_handler import handle_exceptions
from models._sqlite_base import SqliteManagerBase


class MixingDatabaseManager(SqliteManagerBase):
    """`mixing_records.db`만 다루는 매니저 (일반 배합 기록 + 레거시 레시피)."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = DB_FILE
        super().__init__(db_path, log_prefix="데이터베이스")
        self._migrate_legacy_db()
        self._create_tables()
        logger.info(f"데이터베이스 초기화 완료: {self.db_path}")

    def _migrate_legacy_db(self):
        """
        기존 BASE_PATH/resources 위치에 DB가 있고 새 경로에 없으면 복사하여 사용한다.
        Program Files 등 쓰기 제한된 위치에서 실행 시 사용자 프로필로 안전하게 이동하기 위함.
        """
        if os.path.exists(self.db_path):
            return
        if os.path.exists(LEGACY_DB_PATH):
            try:
                import shutil

                os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
                shutil.copy2(LEGACY_DB_PATH, self.db_path)
                logger.info(f"레거시 DB를 신규 경로로 복사했습니다: {self.db_path}")
            except OSError as e:
                logger.warning(f"레거시 DB 복사 실패({LEGACY_DB_PATH} -> {self.db_path}): {e}")

    @handle_exceptions(user_message="데이터베이스 테이블 생성 중 오류가 발생했습니다.")
    def _create_tables(self):
        """필요한 테이블들을 생성"""
        with self.get_connection() as conn:
            # 배합 기록 테이블
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mixing_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_lot TEXT NOT NULL,
                    recipe_name TEXT NOT NULL,
                    worker TEXT NOT NULL,
                    work_date TEXT NOT NULL,
                    work_time TEXT NOT NULL,
                    total_amount REAL NOT NULL,
                    scale TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 배합 상세 기록 테이블
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mixing_details (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mixing_record_id INTEGER NOT NULL,
                    material_code TEXT NOT NULL,
                    material_name TEXT NOT NULL,
                    material_lot TEXT NOT NULL,
                    ratio REAL NOT NULL,
                    theory_amount REAL NOT NULL,
                    actual_amount REAL NOT NULL,
                    sequence_order INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (mixing_record_id) REFERENCES mixing_records (id)
                )
            """)
            
            # 레시피 테이블
            conn.execute("""
                CREATE TABLE IF NOT EXISTS recipes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipe_name TEXT NOT NULL,
                    material_code TEXT NOT NULL,
                    material_name TEXT NOT NULL,
                    ratio REAL NOT NULL,
                    sequence_order INTEGER NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(recipe_name, material_code)
                )
            """)
            
            # 인덱스 생성
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mixing_records_date ON mixing_records(work_date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mixing_records_lot ON mixing_records(product_lot)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_recipes_name ON recipes(recipe_name)")
            self._try_create_unique_lot_index(conn)

            conn.commit()
            logger.debug("데이터베이스 테이블 생성/확인 완료")

    def _try_create_unique_lot_index(self, conn) -> None:
        """기존 데이터에 중복이 없을 때만 product_lot UNIQUE 인덱스를 생성한다."""
        try:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_mixing_records_product_lot ON mixing_records(product_lot)"
            )
        except sqlite3.IntegrityError:
            cursor = conn.execute(
                """
                SELECT product_lot, COUNT(*) AS cnt
                FROM mixing_records
                GROUP BY product_lot
                HAVING COUNT(*) > 1
                LIMIT 1
                """
            )
            dup = cursor.fetchone()
            if dup:
                logger.warning(
                    f"mixing product_lot duplicates found; unique index skipped (sample={dup['product_lot']}, count={dup['cnt']})"
                )
            else:
                logger.warning("mixing product_lot unique index creation skipped due to duplicates")
    
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
        max_seq = 0
        for row in cursor.fetchall():
            lot = row["product_lot"]
            if not lot.startswith(base_lot):
                continue
            try:
                seq = int(lot[len(base_lot):])
            except (ValueError, IndexError):
                continue
            if seq > max_seq:
                max_seq = seq
        return f"{base_lot}{max_seq + 1:02d}"

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
            
            if start_date:
                query += " AND work_date >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND work_date <= ?"
                params.append(end_date)
            
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
    
    @handle_exceptions(user_message="레시피 저장 중 오류가 발생했습니다.")
    def save_recipe(self, recipe_name: str, materials: List[Dict]):
        """레시피를 데이터베이스에 저장합니다."""
        with self.get_connection() as conn:
            # 기존 레시피 비활성화
            conn.execute("""
                UPDATE recipes SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE recipe_name = ?
            """, (recipe_name,))
            
            # 새 레시피 저장
            for i, material in enumerate(materials):
                conn.execute("""
                    INSERT OR REPLACE INTO recipes 
                    (recipe_name, material_code, material_name, ratio, sequence_order)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    recipe_name,
                    material['품목코드'],
                    material['품목명'],
                    material['배합비율'],
                    i + 1
                ))
            
            conn.commit()
            logger.info(f"레시피 저장 완료: {recipe_name}, {len(materials)}개 재료")
    
    @handle_exceptions(user_message="레시피 조회 중 오류가 발생했습니다.", default_return={})
    def get_recipes(self) -> Dict[str, List[Dict]]:
        """활성화된 모든 레시피를 조회합니다."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT recipe_name, material_code, material_name, ratio, sequence_order
                FROM recipes 
                WHERE is_active = 1 
                ORDER BY recipe_name, sequence_order
            """)
            
            recipes = {}
            for row in cursor.fetchall():
                recipe_name = row['recipe_name']
                if recipe_name not in recipes:
                    recipes[recipe_name] = []
                
                recipes[recipe_name].append({
                    '품목코드': row['material_code'],
                    '품목명': row['material_name'],
                    '배합비율': row['ratio']
                })
            
            logger.debug(f"레시피 조회: {len(recipes)}개 레시피")
            return recipes
    
    @handle_exceptions(user_message="데이터베이스 백업 중 오류가 발생했습니다.")
    def backup_database(self, backup_path: Optional[str] = None):
        """데이터베이스를 백업합니다."""
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = os.path.join(USER_DATA_DIR, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, f"mixing_records_backup_{timestamp}.db")
        
        import shutil
        shutil.copy2(self.db_path, backup_path)
        logger.info(f"데이터베이스 백업 완료: {backup_path}")
        return backup_path
    
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
        if start_date:
            query += " AND r.work_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND r.work_date <= ?"
            params.append(end_date)
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
        if start_date:
            query += " AND work_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND work_date <= ?"
            params.append(end_date)
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
        if start_date:
            query += " AND work_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND work_date <= ?"
            params.append(end_date)
        query += " GROUP BY recipe_name ORDER BY run_count DESC LIMIT ?"
        params.append(limit)
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = [dict(row) for row in cursor.fetchall()]
            logger.debug(f"레시피 빈도 TOP-{limit} 조회: {len(rows)}건")
            return rows


__all__ = ["MixingDatabaseManager"]
