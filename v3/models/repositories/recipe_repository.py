"""레시피(`recipes`) 도메인 Repository (PDCA #28).

`MixingDatabaseManager`(Facade)에서 레시피 저장/조회 책임을 분리한 것.
SQL·로그·반환 구조는 분리 이전과 비트-동일하게 유지된다(무동작 변경 리팩토링).
"""
from typing import Dict, List

from utils.logger import logger
from utils.error_handler import handle_exceptions
from models._sqlite_base import SqliteManagerBase


class RecipeRepository(SqliteManagerBase):
    """`recipes` 테이블 전용 Repository."""

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


__all__ = ["RecipeRepository"]
