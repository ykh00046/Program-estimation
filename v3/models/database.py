"""배합 기록(`mixing_records.db`) 전용 데이터베이스 매니저 (Facade).

이 모듈은 일반 배합 작업의 `mixing_records` / `mixing_details` / `recipes` /
`material_stock` 테이블만 다룬다.
DHR(Device History Record) 데이터는 `models.dhr_database.DhrDatabaseManager`를 사용하라.

PDCA #28에서 도메인별 4개 Repository(`models.repositories`)로 분해되었다.
`MixingDatabaseManager`는 공개 진입점을 보존하는 **Facade**로, 테이블 생성/마이그
레이션 같은 인프라만 직접 보유하고 도메인 메서드는 각 Repository에 위임한다.
공개 API(클래스명·시그니처·반환값·로그)는 분해 이전과 비트-동일하다(무동작 변경).

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
from models.repositories import (
    MixingRecordRepository,
    RecipeRepository,
    StatisticsRepository,
    MaterialStockRepository,
)


class MixingDatabaseManager(SqliteManagerBase):
    """`mixing_records.db`만 다루는 Facade (일반 배합 기록 + 레시피 + 재고).

    테이블 생성/레거시 마이그레이션/백업 등 인프라는 직접 보유하고, 도메인
    메서드는 동일 `db_path`를 가리키는 4개 Repository에 위임한다. 각 Repository는
    `SqliteManagerBase.get_connection()`이 호출 시점마다 연결을 열고 닫는 단발성
    컨텍스트라 공유 상태가 없어 같은 파일을 가리켜도 충돌하지 않는다.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = DB_FILE
        super().__init__(db_path, log_prefix="데이터베이스")
        self._migrate_legacy_db()
        self._create_tables()
        # 동일 db_path를 가리키는 도메인 Repository 구성 (테이블은 위에서 이미 보장)
        self._records = MixingRecordRepository(self.db_path)
        self._recipes = RecipeRepository(self.db_path)
        self._stats = StatisticsRepository(self.db_path)
        self._stock = MaterialStockRepository(self.db_path)
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

            # 자재 재고 마스터 테이블 (PDCA: material-stock-threshold-alert)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS material_stock (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    material_code TEXT NOT NULL,
                    material_name TEXT NOT NULL,
                    current_stock REAL NOT NULL DEFAULT 0,
                    min_stock_threshold REAL NOT NULL DEFAULT 0,
                    unit TEXT NOT NULL DEFAULT 'g',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(material_code)
                )
            """)

            # 자재 입출고 이력 테이블 (PDCA #30 inventory_inbound_history, append-only)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS material_stock_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    material_code TEXT NOT NULL,
                    material_name TEXT NOT NULL DEFAULT '',
                    change_type TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    stock_after REAL NOT NULL DEFAULT 0,
                    unit TEXT NOT NULL DEFAULT 'g',
                    note TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 인덱스 생성
            conn.execute("CREATE INDEX IF NOT EXISTS idx_material_stock_code ON material_stock(material_code)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_stock_history_code ON material_stock_history(material_code)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_stock_history_created ON material_stock_history(created_at)")
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

    # ==================================================================
    # 도메인 위임 (Facade) — 공개 API는 분해 이전과 비트-동일
    # ==================================================================

    # ── 배합 기록 (MixingRecordRepository) ──
    def save_mixing_record(self, record_data: Dict, details: List[Dict]) -> int:
        return self._records.save_mixing_record(record_data, details)

    def get_mixing_records(self,
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None,
                          worker: Optional[str] = None,
                          recipe_name: Optional[str] = None,
                          limit: int = 100) -> List[Dict]:
        return self._records.get_mixing_records(start_date, end_date, worker, recipe_name, limit)

    def get_mixing_details(self, mixing_record_id: int) -> List[Dict]:
        return self._records.get_mixing_details(mixing_record_id)

    def delete_mixing_record(self, record_id: int) -> bool:
        return self._records.delete_mixing_record(record_id)

    def get_mixing_record_by_lot(self, product_lot: str) -> Optional[Dict]:
        return self._records.get_mixing_record_by_lot(product_lot)

    def update_mixing_record(self, record_id: int, worker: str, total_amount: float) -> bool:
        return self._records.update_mixing_record(record_id, worker, total_amount)

    def update_mixing_detail(self, record_id: int, material_code: str,
                              material_lot: str, ratio: float,
                              theory_amount: float, actual_amount: float) -> bool:
        return self._records.update_mixing_detail(
            record_id, material_code, material_lot, ratio, theory_amount, actual_amount
        )

    def update_mixing_record_with_details(self, record_id: int, worker: str,
                                          total_amount: float, materials: List[Dict]) -> bool:
        return self._records.update_mixing_record_with_details(record_id, worker, total_amount, materials)

    def get_all_records_with_details(self, limit: int = 10000) -> List[Dict]:
        return self._records.get_all_records_with_details(limit)

    def get_all_material_names(self) -> List[str]:
        return self._records.get_all_material_names()

    # ── 레시피 (RecipeRepository) ──
    def save_recipe(self, recipe_name: str, materials: List[Dict]):
        return self._recipes.save_recipe(recipe_name, materials)

    def get_recipes(self) -> Dict[str, List[Dict]]:
        return self._recipes.get_recipes()

    # ── 통계 집계 (StatisticsRepository) ──
    def get_statistics(self) -> Dict:
        return self._stats.get_statistics()

    def sum_item_amount_by_date_range(self, start_date: str, end_date: str, material_name: str) -> float:
        return self._stats.sum_item_amount_by_date_range(start_date, end_date, material_name)

    def get_monthly_production_stats(self, months: int = 6) -> List[Dict]:
        return self._stats.get_monthly_production_stats(months)

    def get_top_materials(self, limit: int = 10, start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> List[Dict]:
        return self._stats.get_top_materials(limit, start_date, end_date)

    def get_worker_stats(self, start_date: Optional[str] = None,
                         end_date: Optional[str] = None) -> List[Dict]:
        return self._stats.get_worker_stats(start_date, end_date)

    def get_recipe_frequency(self, limit: int = 10, start_date: Optional[str] = None,
                             end_date: Optional[str] = None) -> List[Dict]:
        return self._stats.get_recipe_frequency(limit, start_date, end_date)

    # ── 자재 재고 (MaterialStockRepository) ──
    def get_all_material_stock(self) -> List[Dict]:
        return self._stock.get_all_material_stock()

    def get_low_stock_materials(self, default_threshold: float = 0.0) -> List[Dict]:
        return self._stock.get_low_stock_materials(default_threshold)

    def upsert_material_stock(self, material_code: str, material_name: str,
                              current_stock: float, min_stock_threshold: float,
                              unit: str = "g") -> bool:
        return self._stock.upsert_material_stock(
            material_code, material_name, current_stock, min_stock_threshold, unit
        )

    def seed_material_stock_from_history(self) -> int:
        return self._stock.seed_material_stock_from_history()

    def apply_consumption(self, consumption: List[Dict]) -> int:
        return self._stock.apply_consumption(consumption)

    def add_inbound(self, material_code: str, material_name: str, quantity: float,
                    unit: str = "g", note: str = "") -> bool:
        return self._stock.add_inbound(material_code, material_name, quantity, unit, note)

    def get_stock_history(self, material_code: Optional[str] = None, limit: int = 200) -> List[Dict]:
        return self._stock.get_stock_history(material_code, limit)

    # ==================================================================
    # 인프라 (Facade 직접 보유)
    # ==================================================================

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


__all__ = ["MixingDatabaseManager"]
