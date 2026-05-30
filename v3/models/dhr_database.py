"""DHR(Device History Record) 전용 SQLite 매니저 (PDCA #18).

책임 경계:
- DB 파일: DHR_DB_FILE (기본 dhr_records.db)
- 테이블: dhr_records, dhr_details, dhr_recipes, dhr_recipe_materials, dhr_recipe_categories
- 도메인: DHR 기록 + DHR 전용 레시피 시스템(거래처/제품종류/약품/착용기간)
- product_lot UNIQUE 제약 (PDCA #8)
- Google Sheets 백업 미지원
- 레거시 DB 마이그레이션 없음 (DHR 시스템 자체가 신규)

일반 배합 기록은 MixingDatabaseManager(models.database)가 별도 DB 파일에서 관리한다.
두 매니저는 SqliteManagerBase(models._sqlite_base)를 공유한다.
"""
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

from config.settings import USER_DATA_DIR
from models._sqlite_base import SqliteManagerBase
from models.lot_utils import next_lot
from utils.logger import logger
from utils.error_handler import handle_exceptions, DatabaseError


# DHR 전용 DB 파일 경로
DHR_DB_FILE = os.path.join(USER_DATA_DIR, "dhr_records.db")


class DhrDatabaseManager(SqliteManagerBase):
    """DHR 전용 데이터베이스 관리 클래스"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = DHR_DB_FILE
        super().__init__(db_path, log_prefix="DHR 데이터베이스")
        self._create_tables()
        logger.info(f"DHR 데이터베이스 초기화 완료: {self.db_path}")

    @handle_exceptions(user_message="DHR 테이블 생성 중 오류가 발생했습니다.")
    def _create_tables(self):
        """필요한 테이블들을 생성"""
        with self.get_connection() as conn:
            # DHR 기록 테이블
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dhr_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_lot TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    worker TEXT NOT NULL,
                    work_date TEXT NOT NULL,
                    work_time TEXT NOT NULL,
                    total_amount REAL NOT NULL,
                    scale TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # DHR 상세 기록 테이블
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dhr_details (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dhr_record_id INTEGER NOT NULL,
                    material_code TEXT,
                    material_name TEXT NOT NULL,
                    material_lot TEXT,
                    ratio REAL,
                    theory_amount REAL,
                    actual_amount REAL,
                    sequence_order INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (dhr_record_id) REFERENCES dhr_records (id)
                )
            """)
            
            # --- DHR 레시피 관련 테이블 추가 ---
            
            # 분류 마스터 테이블 (거래처, 제품종류, 약품, 착용기간)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dhr_recipe_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_type TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(category_type, value)
                )
            """)
            
            # DHR 레시피 헤더 테이블
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dhr_recipes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipe_name TEXT NOT NULL,
                    company TEXT,
                    product_type TEXT,
                    drug TEXT,
                    wear_period TEXT,
                    default_amount REAL DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # DHR 레시피 자재 목록 테이블
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dhr_recipe_materials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipe_id INTEGER NOT NULL,
                    material_code TEXT,
                    material_name TEXT NOT NULL,
                    ratio REAL DEFAULT 0,
                    sequence_order INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (recipe_id) REFERENCES dhr_recipes (id)
                )
            """)
            
            # 인덱스 생성
            conn.execute("CREATE INDEX IF NOT EXISTS idx_dhr_records_date ON dhr_records(work_date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_dhr_records_lot ON dhr_records(product_lot)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_dhr_recipes_name ON dhr_recipes(recipe_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_dhr_categories_type ON dhr_recipe_categories(category_type)")
            self._try_create_unique_lot_index(conn)
            
            conn.commit()
            logger.debug("DHR 데이터베이스 테이블 생성/확인 완료")

    def _try_create_unique_lot_index(self, conn) -> None:
        """Create a unique LOT index when existing data has no duplicates."""
        try:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_dhr_records_product_lot ON dhr_records(product_lot)"
            )
        except sqlite3.IntegrityError:
            cursor = conn.execute(
                """
                SELECT product_lot, COUNT(*) AS cnt
                FROM dhr_records
                GROUP BY product_lot
                HAVING COUNT(*) > 1
                LIMIT 1
                """
            )
            dup = cursor.fetchone()
            if dup:
                logger.warning(
                    f"DHR product_lot duplicates found; unique index skipped (sample={dup['product_lot']}, count={dup['cnt']})"
                )
            else:
                logger.warning("DHR product_lot unique index creation skipped due to duplicates")

    def _generate_product_lot_with_conn(self, conn, product_name: str, work_date: str) -> str:
        target_date = datetime.strptime(work_date, "%Y-%m-%d")
        date_str = target_date.strftime("%y%m%d")
        base_lot = f"{product_name}{date_str}"
        cursor = conn.execute(
            "SELECT product_lot FROM dhr_records WHERE work_date = ? AND product_name = ?",
            (work_date, product_name),
        )
        return next_lot(base_lot, (row["product_lot"] for row in cursor.fetchall()))

    def _resolve_unique_product_lot(self, conn, record_data: Dict) -> str:
        requested_lot = str(record_data.get("product_lot", "")).strip()
        if requested_lot:
            cursor = conn.execute(
                "SELECT 1 FROM dhr_records WHERE product_lot = ? LIMIT 1",
                (requested_lot,),
            )
            if cursor.fetchone() is None:
                return requested_lot
            logger.warning(f"Duplicate DHR product_lot detected; regenerating ({requested_lot})")

        product_name = str(record_data.get("product_name", "")).strip()
        work_date = str(record_data.get("work_date", "")).strip()
        if not product_name or not work_date:
            raise ValueError("product_name and work_date are required to generate a unique DHR LOT")
        return self._generate_product_lot_with_conn(conn, product_name, work_date)
    
    @handle_exceptions(user_message="DHR 기록 저장 중 오류가 발생했습니다.")
    def generate_product_lot(self, product_name: str, work_date: str) -> str:
        """DHR product LOT generator ({product_name}{YYMMDD}{seq:02d})."""
        target_date = datetime.strptime(work_date, "%Y-%m-%d")
        date_str = target_date.strftime("%y%m%d")
        base_lot = f"{product_name}{date_str}"

        try:
            with self.get_connection() as conn:
                return self._generate_product_lot_with_conn(conn, product_name, work_date)
        except (sqlite3.Error, DatabaseError) as e:
            # get_connection이 sqlite3.Error를 DatabaseError로 변환하므로 둘 다 포착해야
            # fallback이 실제로 동작한다(post-#18 잠재 버그 교정).
            logger.error(f"DHR LOT 생성 중 오류: {e}. 기본 LOT를 사용합니다.")
            return f"{base_lot}01"

    def save_dhr_record(self, record_data: Dict, details: List[Dict]) -> int:
        """
        DHR 기록을 저장합니다.
        
        Args:
            record_data: 기본 정보
            details: 상세 정보 리스트
        
        Returns:
            저장된 레코드의 ID
        """
        with self.get_connection() as conn:
            resolved_lot = self._resolve_unique_product_lot(conn, record_data)
            record_data["product_lot"] = resolved_lot
            # 기본 기록 저장
            cursor = conn.execute("""
                INSERT INTO dhr_records 
                (product_lot, product_name, worker, work_date, work_time, total_amount, scale)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                resolved_lot,
                record_data.get('product_name', ''),
                record_data['worker'],
                record_data['work_date'],
                record_data.get('work_time', ''),
                record_data['total_amount'],
                record_data.get('scale', '')
            ))
            
            record_id = cursor.lastrowid
            
            # 상세 기록 저장
            for i, detail in enumerate(details):
                conn.execute("""
                    INSERT INTO dhr_details 
                    (dhr_record_id, material_code, material_name, material_lot, 
                     ratio, theory_amount, actual_amount, sequence_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record_id,
                    detail.get('material_code', ''),
                    detail.get('material_name', ''),
                    detail.get('material_lot', ''),
                    detail.get('ratio', 0),
                    detail.get('theory_amount', 0),
                    detail.get('actual_amount', 0),
                    i + 1
                ))
            
            conn.commit()
            logger.info(f"DHR 기록 저장 완료: LOT {record_data['product_lot']}, ID {record_id}")
            return record_id
    
    @handle_exceptions(user_message="DHR 기록 조회 중 오류가 발생했습니다.", default_return=[])
    def get_dhr_records(self, 
                        start_date: Optional[str] = None,
                        end_date: Optional[str] = None,
                        limit: int = 100) -> List[Dict]:
        """
        DHR 기록을 조회합니다.
        """
        with self.get_connection() as conn:
            query = "SELECT * FROM dhr_records WHERE 1=1"
            params = []

            query = self._append_date_range(query, params, start_date, end_date)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(query, params)
            records = [dict(row) for row in cursor.fetchall()]
            
            logger.debug(f"DHR 기록 조회: {len(records)}건")
            return records
    
    @handle_exceptions(user_message="DHR 상세 정보 조회 중 오류가 발생했습니다.", default_return=[])
    def get_dhr_details(self, dhr_record_id: int) -> List[Dict]:
        """특정 DHR 기록의 상세 정보를 조회합니다."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM dhr_details 
                WHERE dhr_record_id = ? 
                ORDER BY sequence_order
            """, (dhr_record_id,))
            
            details = [dict(row) for row in cursor.fetchall()]
            logger.debug(f"DHR 상세 조회: 레코드ID {dhr_record_id}, {len(details)}건")
            return details

    @handle_exceptions(user_message="DHR 기록 조회 중 오류가 발생했습니다.", default_return=None)
    def get_dhr_record_by_lot(self, product_lot: str) -> Optional[Dict]:
        """제품 LOT 번호로 DHR 기록을 조회합니다."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM dhr_records WHERE product_lot = ?", (product_lot,))
            record = cursor.fetchone()

            if record:
                return dict(record)
            return None
    
    @handle_exceptions(user_message="DHR 기록 삭제 중 오류가 발생했습니다.")
    def delete_dhr_record(self, record_id: int) -> bool:
        """DHR 기록을 삭제합니다."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT product_lot FROM dhr_records WHERE id = ?", (record_id,))
            record = cursor.fetchone()

            if not record:
                logger.warning(f"삭제할 DHR 레코드를 찾을 수 없습니다: ID {record_id}")
                return False

            product_lot = record['product_lot']

            # 상세 정보 먼저 삭제
            conn.execute("DELETE FROM dhr_details WHERE dhr_record_id = ?", (record_id,))

            # 기본 레코드 삭제
            conn.execute("DELETE FROM dhr_records WHERE id = ?", (record_id,))

            conn.commit()
            logger.info(f"DHR 기록 삭제 완료: ID {record_id}, LOT {product_lot}")
            return True

    # ========== DHR 레시피 관리 메서드 ==========
    
    @handle_exceptions(user_message="분류 항목 저장 중 오류가 발생했습니다.")
    def add_category(self, category_type: str, value: str) -> int:
        """분류 항목을 추가합니다."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT OR IGNORE INTO dhr_recipe_categories (category_type, value)
                VALUES (?, ?)
            """, (category_type, value))
            conn.commit()
            return cursor.lastrowid
    
    @handle_exceptions(user_message="분류 항목 조회 중 오류가 발생했습니다.", default_return=[])
    def get_categories(self, category_type: str) -> List[str]:
        """특정 분류 타입의 모든 값을 조회합니다."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT value FROM dhr_recipe_categories 
                WHERE category_type = ? ORDER BY value
            """, (category_type,))
            return [row['value'] for row in cursor.fetchall()]
    
    @handle_exceptions(user_message="레시피 저장 중 오류가 발생했습니다.")
    def save_recipe(self, recipe_data: Dict, materials: List[Dict]) -> int:
        """DHR 레시피를 저장합니다."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO dhr_recipes 
                (recipe_name, company, product_type, drug, wear_period, default_amount)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                recipe_data['recipe_name'],
                recipe_data.get('company', ''),
                recipe_data.get('product_type', ''),
                recipe_data.get('drug', ''),
                recipe_data.get('wear_period', ''),
                recipe_data.get('default_amount', 0)
            ))
            
            recipe_id = cursor.lastrowid
            
            # 자재 목록 저장
            for i, mat in enumerate(materials):
                conn.execute("""
                    INSERT INTO dhr_recipe_materials 
                    (recipe_id, material_code, material_name, ratio, sequence_order)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    recipe_id,
                    mat.get('material_code', ''),
                    mat.get('material_name', ''),
                    mat.get('ratio', 0),
                    i + 1
                ))
            
            # 분류 마스터에 자동 추가
            for cat_type, value in [
                ('company', recipe_data.get('company')),
                ('product_type', recipe_data.get('product_type')),
                ('drug', recipe_data.get('drug')),
                ('wear_period', recipe_data.get('wear_period'))
            ]:
                if value:
                    conn.execute("""
                        INSERT OR IGNORE INTO dhr_recipe_categories (category_type, value)
                        VALUES (?, ?)
                    """, (cat_type, value))
            
            conn.commit()
            logger.info(f"DHR 레시피 저장 완료: {recipe_data['recipe_name']}, ID {recipe_id}")
            return recipe_id
    
    @handle_exceptions(user_message="레시피 조회 중 오류가 발생했습니다.", default_return=[])
    def get_recipes(self, company: Optional[str] = None, product_type: Optional[str] = None,
                    drug: Optional[str] = None, wear_period: Optional[str] = None) -> List[Dict]:
        """조건에 맞는 레시피 목록을 조회합니다."""
        with self.get_connection() as conn:
            query = "SELECT * FROM dhr_recipes WHERE is_active = 1"
            params = []
            
            if company:
                query += " AND company = ?"
                params.append(company)
            if product_type:
                query += " AND product_type = ?"
                params.append(product_type)
            if drug:
                query += " AND drug = ?"
                params.append(drug)
            if wear_period:
                query += " AND wear_period = ?"
                params.append(wear_period)
            
            query += " ORDER BY recipe_name"
            
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    @handle_exceptions(user_message="레시피 자재 조회 중 오류가 발생했습니다.", default_return=[])
    def get_recipe_materials(self, recipe_id: int) -> List[Dict]:
        """특정 레시피의 자재 목록을 조회합니다."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM dhr_recipe_materials 
                WHERE recipe_id = ? ORDER BY sequence_order
            """, (recipe_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    @handle_exceptions(user_message="레시피 삭제 중 오류가 발생했습니다.")
    def delete_recipe(self, recipe_id: int) -> bool:
        """레시피를 삭제합니다."""
        with self.get_connection() as conn:
            # 자재 목록 먼저 삭제
            conn.execute("DELETE FROM dhr_recipe_materials WHERE recipe_id = ?", (recipe_id,))
            # 레시피 삭제
            conn.execute("DELETE FROM dhr_recipes WHERE id = ?", (recipe_id,))
            conn.commit()
            logger.info(f"DHR 레시피 삭제 완료: ID {recipe_id}")
            return True
    
    @handle_exceptions(user_message="레시피 수정 중 오류가 발생했습니다.")
    def update_recipe(self, recipe_id: int, recipe_data: Dict, materials: List[Dict]) -> bool:
        """레시피를 수정합니다."""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE dhr_recipes SET 
                    recipe_name = ?, company = ?, product_type = ?, 
                    drug = ?, wear_period = ?, default_amount = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                recipe_data['recipe_name'],
                recipe_data.get('company', ''),
                recipe_data.get('product_type', ''),
                recipe_data.get('drug', ''),
                recipe_data.get('wear_period', ''),
                recipe_data.get('default_amount', 0),
                recipe_id
            ))
            
            # 기존 자재 삭제 후 재삽입
            conn.execute("DELETE FROM dhr_recipe_materials WHERE recipe_id = ?", (recipe_id,))
            
            for i, mat in enumerate(materials):
                conn.execute("""
                    INSERT INTO dhr_recipe_materials 
                    (recipe_id, material_code, material_name, ratio, sequence_order)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    recipe_id,
                    mat.get('material_code', ''),
                    mat.get('material_name', ''),
                    mat.get('ratio', 0),
                    i + 1
                ))
            
            conn.commit()
            logger.info(f"DHR 레시피 수정 완료: ID {recipe_id}")
            return True
