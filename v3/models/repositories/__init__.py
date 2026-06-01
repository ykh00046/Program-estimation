"""도메인별 SQLite Repository 패키지 (PDCA #28).

`MixingDatabaseManager`(Facade)가 위임하는 4개 도메인 Repository를 제공한다.
모두 `models._sqlite_base.SqliteManagerBase`를 상속하며 동일한 `mixing_records.db`
파일 경로를 공유한다. 테이블 생성/마이그레이션은 Facade가 담당하고,
각 Repository는 도메인 메서드만 보유한다.
"""
from models.repositories.mixing_record_repository import MixingRecordRepository
from models.repositories.recipe_repository import RecipeRepository
from models.repositories.statistics_repository import StatisticsRepository
from models.repositories.material_stock_repository import MaterialStockRepository

__all__ = [
    "MixingRecordRepository",
    "RecipeRepository",
    "StatisticsRepository",
    "MaterialStockRepository",
]
