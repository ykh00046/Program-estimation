"""
데이터 관리 기능의 리팩토링 버전.
기존 Excel 기반 저장 방식에서 SQLite 데이터베이스를 사용하도록 변경합니다.
"""
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
from config.config_manager import config
from config.google_sheets_config import GoogleSheetsConfig
from config.settings import LOT_FILE, RECIPE_FILE
from models.backup.google_sheets_backup import GoogleSheetsBackup
from models.database import MixingDatabaseManager
from models.inventory_alert import MaterialAlert, evaluate_inventory_alerts
from models.repositories.material_stock_repository import CONSUME_NOTE_FMT, RETRO_NOTE_FMT
from models.lot_manager import LotManager
from models.lot_utils import next_lot
from utils.logger import logger


class DataManager:
    """데이터 관리 클래스 (DB 기반)"""

    def __init__(self):
        self.db_manager = MixingDatabaseManager()
        self.lot_manager = LotManager(LOT_FILE)
        self.google_sheets_config = GoogleSheetsConfig()
        self.google_sheets_backup = GoogleSheetsBackup(self.google_sheets_config)
        self.recipes = self._load_recipes_from_excel()

    def _load_recipes_from_excel(self) -> Dict:
        """
        초기 레시피를 Excel 파일로부터 메모리로 로드합니다.
        UI의 레시피 선택 콤보박스를 채우기 위해 사용됩니다.
        """
        recipes = {}
        try:
            if os.path.exists(RECIPE_FILE):
                dtype_spec = {
                    '레시피': str,
                    '품목코드': str,
                    '품목명': str,
                }
                df = pd.read_excel(RECIPE_FILE, engine='openpyxl', dtype=dtype_spec)
                for _, row in df.iterrows():
                    recipe_name = str(row.get('레시피', '')).strip()
                    if not recipe_name:
                        continue
                    
                    recipes.setdefault(recipe_name, []).append({
                        '품목코드': str(row.get('품목코드', '')).strip(),
                        '품목명': str(row.get('품목명', '')).strip(),
                        '배합비율': float(row.get('배합비율', 0.0) or 0.0),
                        '순서': int(row.get('순서', 0) or 0),
                    })
            logger.info(f"Excel에서 레시피 로드 완료: {len(recipes)}종")
            return recipes
        except (OSError, IOError) as e:
            logger.error(f"레시피 Excel 파일 로드 실패: {e}")
            return {}

    def generate_product_lot(self, recipe_name: str, work_date: str) -> str:
        """데이터베이스를 기반으로 제품 LOT 번호를 생성합니다.

        Args:
            recipe_name: 레시피 이름
            work_date: 작업 날짜 (yyyy-MM-dd 형식)
        """
        target_date = datetime.strptime(work_date, "%Y-%m-%d")
        date_str = target_date.strftime("%y%m%d")
        base_lot = f"{recipe_name}{date_str}"

        try:
            # 해당 날짜로 생성된 동일 레시피의 모든 기록을 조회
            today_records = self.db_manager.get_mixing_records(
                start_date=target_date.strftime("%Y-%m-%d"),
                recipe_name=recipe_name,
                limit=1000 # 하루에 1000개 이상은 생성하지 않는다고 가정
            )
            
            # LOT 번호에서 시퀀스 부분만 추출하여 다음 번호를 생성
            return next_lot(base_lot, (record['product_lot'] for record in today_records))
        except (ValueError, OSError) as e:
            logger.error(f"DB 기반 LOT 번호 생성 실패: {e}. 기본값으로 대체합니다.")
            return f"{base_lot}01"
    def _build_record_data(self, product_lot: str, recipe_name: str, worker_name: str,
                           mixing_amount: float, work_date: str, work_time: str) -> Dict:
        """Build base record for DB save."""
        return {
            'product_lot': product_lot,
            'recipe_name': recipe_name,
            'worker': worker_name,
            'work_date': work_date,
            'work_time': work_time,
            'total_amount': mixing_amount,
            'scale': config.default_scale,
        }

    def _build_details_data(self, materials_data: Dict) -> List[Dict]:
        """Build detail rows for DB save."""
        details_data = []
        for idx, (name, data) in enumerate(materials_data.items(), start=1):
            details_data.append({
                'material_code': data.get('품목코드', name),
                'material_name': data.get('품목명', name),
                'material_lot': str(data.get('LOT', '')),
                'ratio': data.get('배합비율', 0.0),
                'theory_amount': data.get('이론계량', 0.0),
                'actual_amount': data.get('실제배합', 0.0),
                'sequence_order': idx,
            })
        return details_data

    @staticmethod
    def _build_backup_records(record_data: Dict, details: List[Dict]) -> List[Dict]:
        """Sheets 백업용 행 목록(기록+상세 결합)을 만든다 (PDCA #33 추출)."""
        records_for_backup = []
        for detail_item in details:
            combined_record = {
                '제품LOT': record_data.get('product_lot', ''),
                '레시피명': record_data.get('recipe_name', ''),
                '작업자': record_data.get('worker', ''),
                '작업일자': record_data.get('work_date', ''),
                '작업시간': record_data.get('work_time', ''),
                '총배합량': record_data.get('total_amount', 0.0),
                '스케일': record_data.get('scale', ''),
                '품목코드': detail_item.get('material_code', ''),
                '품목명': detail_item.get('material_name', ''),
                '자재LOT': detail_item.get('material_lot', ''),
                '배합비율': detail_item.get('ratio', 0.0),
                '이론량': detail_item.get('theory_amount', 0.0),
                '실제량': detail_item.get('actual_amount', 0.0),
                '순서': detail_item.get('sequence_order', 0)
            }
            records_for_backup.append(combined_record)
        return records_for_backup

    def _is_auto_backup_active(self) -> bool:
        """저장 시 자동 백업이 켜져 있는지 여부."""
        return (self.google_sheets_config.is_backup_enabled() and
                self.google_sheets_config.is_auto_backup_on_save())

    def _backup_to_google_sheets(self, record_data: Dict, details: List[Dict]) -> None:
        """Auto-backup mixing records to Google Sheets."""
        if not self._is_auto_backup_active():
            return

        try:
            records_for_backup = self._build_backup_records(record_data, details)
            success, msg = self.google_sheets_backup.backup_records(records_for_backup)
            if success:
                logger.info(f"Google Sheets auto-backup success: {msg}")
            else:
                logger.warning(f"Google Sheets auto-backup failed: {msg}")
        except (OSError, ValueError, RuntimeError) as e:
            logger.error(f"Google Sheets auto-backup error: {e}")

    def backup_lot_to_sheets(self, product_lot: str) -> Tuple[bool, str]:
        """저장된 LOT을 DB에서 재조회해 Google Sheets로 백업한다 (PDCA #33).

        UI가 워커 스레드에서 호출하는 동기 메서드 — DB가 진실의 원천이므로
        저장된 내용 그대로 백업된다. SQLite 연결은 호출마다 새로 열려 스레드 안전.
        """
        if not self._is_auto_backup_active():
            return False, "Google Sheets 백업이 비활성화되어 있습니다."
        record = self.db_manager.get_mixing_record_by_lot(product_lot)
        if not record:
            return False, f"백업할 기록을 찾을 수 없습니다: LOT {product_lot}"
        details = [dict(d) for d in self.db_manager.get_mixing_details(record['id'])]
        records_for_backup = self._build_backup_records(dict(record), details)
        success, msg = self.google_sheets_backup.backup_records(records_for_backup)
        if success:
            logger.info(f"Google Sheets auto-backup success: {msg}")
        else:
            logger.warning(f"Google Sheets auto-backup failed: {msg}")
        return success, msg
    def validate_record_inputs(self, worker_name: str, recipe_name: str,
                               mixing_amount: float, materials_data: Dict) -> Tuple[bool, str]:
        """Validate required inputs before saving a record."""
        if not worker_name:
            return False, "작업자를 선택해 주세요."
        if not recipe_name.strip():
            return False, "레시피를 선택해주세요."
        if not mixing_amount > 0:
            return False, "배합량을 입력해주세요."
        if not materials_data:
            return False, "원료 정보가 없습니다."
        for _, data in materials_data.items():
            lot = str(data.get("LOT", "")).strip()
            if not lot:
                return False, "자재LOT가 비어 있습니다."
            actual = data.get("실제배합", data.get("actual_amount", 0))
            try:
                actual_val = float(actual)
            except (TypeError, ValueError):
                actual_val = 0.0
            if actual_val <= 0:
                return False, "실제 배합량을 입력해주세요."
        return True, ""

    def save_record(self, worker_name: str, recipe_name: str, mixing_amount: float, materials_data: Dict, work_date: str, work_time: str, signature_options: Optional[Dict] = None, effects_params: Optional[Dict] = None, include_work_time: bool = True, auto_backup: bool = True) -> str:
        """Save mixing record to DB and trigger backup.

        auto_backup=False면 동기 백업을 생략한다 — 호출자(UI)가
        backup_lot_to_sheets를 워커 스레드에서 별도로 실행하는 경우 (PDCA #33).
        """
        try:
            product_lot = self.generate_product_lot(recipe_name, work_date)

            # 1. Build data
            work_time_to_save = work_time if include_work_time else ""
            record_data = self._build_record_data(
                product_lot=product_lot,
                recipe_name=recipe_name,
                worker_name=worker_name,
                mixing_amount=mixing_amount,
                work_date=work_date,
                work_time=work_time_to_save,
            )
            details_data = self._build_details_data(materials_data)

            # 2. Persist (DB가 동일 트랜잭션에서 product_lot 유일성을 최종 보장)
            self.db_manager.save_mixing_record(record_data, details_data)
            product_lot = record_data['product_lot']
            if auto_backup:
                self._backup_to_google_sheets(record_data, details_data)
            self._deduct_inventory(details_data, product_lot)
            logger.info(f"배합 저장: LOT {product_lot}")

            # 3. Export disabled (use record view)
            # self._export_report(record_data, details_data, signature_options, effects_params, include_work_time)

            return product_lot
        except Exception as e:
            logger.critical(f"배합 기록 저장 실패: {e}", exc_info=True)
            raise

    def _deduct_inventory(self, details: List[Dict], product_lot: str = "") -> None:
        """배합 저장 후 자재 재고를 자동 차감한다(설정 on일 때, best-effort).

        차감 실패는 생산 기록 저장을 롤백시키지 않는다(생산 기록이 1순위 진실).
        CONSUME 이력 note에 LOT 마커를 남겨 미차감 검출(PDCA #34)을 가능하게 한다.
        """
        if not self.get_auto_deduct_on_save():
            return
        try:
            consumption = [
                {
                    "material_code": (str(d.get("material_code") or "").strip()
                                      or str(d.get("material_name") or "").strip()),
                    "actual_amount": d.get("actual_amount", 0.0),
                }
                for d in (details or [])
            ]
            note = (CONSUME_NOTE_FMT.format(lot=product_lot)
                    if product_lot else "배합 자동 차감")
            updated = self.db_manager.apply_consumption(consumption, note)
            if updated:
                logger.info(f"재고 자동 차감 완료: {updated}건")
        except Exception as e:  # noqa: BLE001 — 차감 실패가 저장을 막지 않음
            logger.warning(f"재고 자동 차감 실패(저장은 정상): {e}")

    # ------------------------------------------------------------------
    # 재고 정합성 검사 / 보정 (PDCA #34 inventory_reconcile)
    # ------------------------------------------------------------------

    def check_ledger_consistency(self) -> List[Dict]:
        """현재고 vs 장부(최근 stock_after) 불일치 자재 목록."""
        return self.db_manager.check_ledger_consistency()

    def record_reconcile_entry(self, material_code: str) -> bool:
        """장부 체인을 현재고에 정렬 (재고 불변, ADJUST 이력 1건)."""
        return self.db_manager.record_reconcile_entry(material_code)

    def find_undeducted_lots(self, start_date: str, end_date: str) -> List[Dict]:
        """기간 내 미차감 의심 배합 LOT 목록."""
        return self.db_manager.find_undeducted_lots(start_date, end_date)

    def retro_deduct_lots(self, lots: List[str]) -> int:
        """선택 LOT들의 자재 사용량을 소급 차감한다 (ADJUST, note에 LOT 마커).

        Returns: 실제 차감이 적용된 LOT 수 (기록 없거나 자재 미매칭 LOT은 스킵).
        """
        applied = 0
        for lot in lots or []:
            record = self.db_manager.get_mixing_record_by_lot(lot)
            if not record:
                logger.warning(f"소급 차감 스킵: 기록 없음 (LOT {lot})")
                continue
            details = self.db_manager.get_mixing_details(record['id'])
            items = [
                {"material_code": self._norm_code(dict(d)),
                 "delta": -float(dict(d).get("actual_amount") or 0.0)}
                for d in (details or [])
            ]
            updated = self.db_manager.apply_adjustment(
                items, note=RETRO_NOTE_FMT.format(lot=lot))
            if updated:
                applied += 1
                logger.info(f"소급 차감 완료: LOT {lot} ({updated}종)")
        return applied

    def apply_adjustment(self, items: List[Dict], note: str = "재고 조정") -> int:
        """부호 있는 델타로 자재 재고를 조정하고 MOVE_ADJUST 이력을 기록 (PDCA #31)."""
        return self.db_manager.apply_adjustment(items, note)

    @staticmethod
    def _norm_code(d: Dict) -> str:
        """저장 차감과 동일한 정규화: material_code 우선, 없으면 material_name."""
        return (str(d.get("material_code") or "").strip()
                or str(d.get("material_name") or "").strip())

    def _reverse_inventory(self, details: List[Dict], note: str) -> None:
        """details의 actual_amount만큼 재고를 원복(+)한다(설정 on, best-effort).

        원복 실패는 배합 기록 삭제/수정을 롤백시키지 않는다(생산 기록이 1순위 진실).
        """
        if not self.get_auto_deduct_on_save():
            return
        try:
            items = [
                {"material_code": self._norm_code(d),
                 "delta": float(d.get("actual_amount") or 0.0)}
                for d in (details or [])
            ]
            items = [it for it in items if it["material_code"] and it["delta"] > 0]
            if not items:
                return
            updated = self.db_manager.apply_adjustment(items, note)
            if updated:
                logger.info(f"재고 원복 완료: {updated}건 ({note})")
        except Exception as e:  # noqa: BLE001 — 원복 실패가 삭제/수정을 막지 않음
            logger.warning(f"재고 원복 실패(작업은 정상): {e}")

    def _readjust_inventory(self, old_details: List[Dict],
                            new_materials: List[Dict]) -> None:
        """수정 시: old 사용량 원복(+) + new 사용량 재차감(-)을 자재당 2건의
        MOVE_ADJUST로 분리 기록한다(설정 on, best-effort)."""
        if not self.get_auto_deduct_on_save():
            return
        try:
            plus = [
                {"material_code": self._norm_code(d),
                 "delta": float(d.get("actual_amount") or 0.0)}
                for d in (old_details or [])
            ]
            plus = [it for it in plus if it["material_code"] and it["delta"] > 0]
            if plus:
                self.db_manager.apply_adjustment(plus, "배합 수정 원복")
            minus = [
                {"material_code": self._norm_code(d),
                 "delta": -float(d.get("actual_amount") or 0.0)}
                for d in (new_materials or [])
            ]
            minus = [it for it in minus if it["material_code"] and it["delta"] < 0]
            if minus:
                self.db_manager.apply_adjustment(minus, "배합 수정 재차감")
            logger.info("재고 재정산 완료(수정)")
        except Exception as e:  # noqa: BLE001 — 재정산 실패가 수정을 막지 않음
            logger.warning(f"재고 재정산 실패(수정은 정상): {e}")

    def _generate_report_files(self, export_data: Dict, worker_name: str,
                               signature_cfg: Dict, effects_params: Optional[Dict],
                               include_work_time: bool = True) -> Optional[str]:
        """서명 이미지/Excel/PDF 공통 생성 로직.

        Returns:
            생성된 PDF 파일 경로, 실패 시 None.
        """
        from models.excel_exporter import ExcelExporter
        from models.image_processor import ImageProcessor

        base_dir = os.path.dirname(os.path.dirname(__file__))
        resources_path = os.path.join(base_dir, 'resources', 'signature')
        base_image_path = os.path.join(resources_path, 'image.jpeg')
        signed_image_path = os.path.join(base_dir, 'resources', f"temp_signed_{worker_name}.png")
        debug_path = os.path.join(base_dir, '실적서', 'debug_images')

        img_processor = ImageProcessor(resources_path=resources_path, config=signature_cfg)
        success, msg = img_processor.create_signed_image(
            base_image_path, signed_image_path, worker_name, debug_path=debug_path
        )
        image_to_embed = signed_image_path if success else base_image_path
        if not success:
            logger.warning(f"서명 이미지 생성 실패: {msg}. 기본 이미지로 대체합니다.")

        exporter = ExcelExporter()
        excel_file = exporter.export_to_excel(
            export_data,
            include_image=True,
            image_path=image_to_embed,
            include_work_time=include_work_time
        )

        pdf_file = None
        if excel_file:
            pdf_file = exporter.export_to_pdf(excel_file, effects_params)
            if pdf_file:
                logger.info(f"실적서 생성 완료: {pdf_file}")

        if success and os.path.exists(signed_image_path):
            try:
                os.remove(signed_image_path)
            except OSError:
                pass

        return pdf_file

    def _export_report(self, record_data: Dict, details_data: List[Dict], signature_options: Optional[Dict], effects_params: Optional[Dict], include_work_time: bool = True):
        """실적서(Excel/PDF)를 생성하는 내부 헬퍼 메서드"""
        try:
            signature_cfg = config.get('signature', {})
            if signature_options:
                signature_cfg['include'] = signature_options

            export_data = record_data.copy()
            export_data['materials'] = details_data

            pdf_file = self._generate_report_files(
                export_data, record_data['worker'], signature_cfg,
                effects_params, include_work_time
            )
            if pdf_file:
                try:
                    import shutil
                    base_dir = os.path.dirname(os.path.dirname(__file__))
                    final_pdf_dir = os.path.join(base_dir, '실적서', 'pdf')
                    os.makedirs(final_pdf_dir, exist_ok=True)
                    shutil.move(pdf_file, os.path.join(final_pdf_dir, os.path.basename(pdf_file)))
                except OSError as move_err:
                    logger.warning(f"PDF 위치 정규화 실패: {move_err}")
        except (OSError, IOError) as e:
            logger.error(f"실적서 생성 중 오류 발생: {e}", exc_info=True)
    
    def get_mixing_records(self, start_date: Optional[str] = None, end_date: Optional[str] = None,
                           worker: Optional[str] = None, recipe_name: Optional[str] = None,
                           limit: int = 100) -> List[Dict]:
        """배합 기록을 조건 조회합니다."""
        return self.db_manager.get_mixing_records(
            start_date=start_date, end_date=end_date,
            worker=worker, recipe_name=recipe_name, limit=limit
        )

    def get_all_records_df(self) -> pd.DataFrame:
        """모든 배합 기록을 DataFrame으로 반환합니다 (단일 JOIN 쿼리)."""
        try:
            rows = self.db_manager.get_all_records_with_details(limit=10000)
            if not rows:
                return pd.DataFrame()
            return pd.DataFrame(rows)
        except (sqlite3.Error, ValueError) as e:
            logger.error(f"모든 기록 조회 실패: {e}")
            return pd.DataFrame()

    def delete_record(self, product_lot: str) -> bool:
        """
        제품 LOT 번호로 배합 기록을 삭제합니다.
        """
        try:
            record = self.db_manager.get_mixing_record_by_lot(product_lot)
            if not record:
                logger.warning(f"삭제할 기록을 찾을 수 없습니다: LOT {product_lot}")
                return False

            # 삭제 전에 차감분 스냅샷(삭제 후엔 mixing_details가 사라짐)
            old_details = self.db_manager.get_mixing_details(record['id'])
            success = self.db_manager.delete_mixing_record(record['id'])
            if success:
                self._reverse_inventory(old_details, "배합 기록 삭제 원복")
                logger.info(f"배합 기록 삭제 완료: LOT {product_lot}")
            return success
        except (sqlite3.Error, ValueError) as e:
            logger.error(f"배합 기록 삭제 오류: {e}", exc_info=True)
            return False
    
    def update_record(self, product_lot: str, worker: str, total_amount: float, materials: List[Dict]) -> bool:
        """
        배합 기록을 수정합니다.
        
        Args:
            product_lot: 제품 LOT 번호
            worker: 작업자 이름
            total_amount: 배합량
            materials: 재료 정보 리스트 (material_code, material_lot, ratio, theory_amount, actual_amount)
        """
        try:
            record = self.db_manager.get_mixing_record_by_lot(product_lot)
            if not record:
                logger.warning(f"수정할 기록을 찾을 수 없습니다: LOT {product_lot}")
                return False
            
            record_id = record['id']
            old_details = self.db_manager.get_mixing_details(record_id)  # 수정 전 스냅샷

            # 기본 기록 + 상세 자재를 단일 트랜잭션으로 수정 (부분 실패 시 전체 롤백)
            success = self.db_manager.update_mixing_record_with_details(
                record_id=record_id,
                worker=worker,
                total_amount=total_amount,
                materials=materials,
            )
            if not success:
                return False

            # old 사용량 원복(+) + new 사용량 재차감(-) → 자재당 2건 ADJUST 이력
            self._readjust_inventory(old_details, materials)
            logger.info(f"배합 기록 수정 완료: LOT {product_lot}")
            return True
        except (sqlite3.Error, ValueError) as e:
            logger.error(f"배합 기록 수정 오류: {e}", exc_info=True)
            return False

    def export_existing_record(self, product_lot: str, effects_params: Optional[Dict] = None, include_work_time: bool = True) -> Optional[str]:
        """저장된 배합 기록으로 엑셀/PDF를 재출력합니다."""
        try:
            record = self.db_manager.get_mixing_record_by_lot(product_lot)
            if not record:
                logger.warning(f"출력할 기록을 찾을 수 없습니다: LOT {product_lot}")
                return None

            details = self.db_manager.get_mixing_details(record['id'])
            if not details:
                logger.warning(f"출력할 상세 정보가 없습니다: LOT {product_lot}")
                return None

            export_data = {
                'product_lot': record['product_lot'],
                'worker': record['worker'],
                'total_amount': record['total_amount'],
                'work_date': record['work_date'],
                'work_time': record['work_time'],
                'scale': record['scale'],
                'materials': [dict(d) for d in details]
            }

            signature_cfg = config.get('signature', {})
            pdf_file = self._generate_report_files(
                export_data, record['worker'], signature_cfg,
                effects_params, include_work_time
            )
            if pdf_file:
                logger.info(f"기존 기록 재출력 완료: {pdf_file}")
            return pdf_file
        except (sqlite3.Error, OSError, ValueError) as e:
            logger.error(f"기존 기록 재출력 오류: {e}", exc_info=True)
            return None

# 필요한 경우, 레거시 Excel 기반 함수들을 여기에 남겨두거나 점진적으로 DB 기반으로 전환할 수 있습니다.
# 예: def update_material_lots 등

    def find_material_lot(self, item_code: str, work_date: str) -> List[Tuple[str, str]]:
        """
        Finds suitable LOTs for a given material and work date.

        Args:
            item_code: The item code of the material.
            work_date: The work date selected by the user.

        Returns:
            A list of suitable LOT numbers.
        """
        return self.lot_manager.get_lot(item_code, work_date)

    def get_all_material_names(self) -> List[str]:
        """
        Retrieves a unique list of all material names from the database.
        """
        return self.db_manager.get_all_material_names()

    def get_total_amount_for_item(self, start_date: str, end_date: str, material_name: str) -> float:
        """
        Calculates the total mixed amount for a specific item within a date range.
        """
        return self.db_manager.sum_item_amount_by_date_range(start_date, end_date, material_name)

    def get_recipe_names(self) -> List[str]:
        """Return sorted recipe names."""
        return sorted(self.recipes.keys())

    def get_recipe_items(self, recipe_name: str) -> List[Dict]:
        """Return recipe items for the given recipe name."""
        return self.recipes.get(recipe_name, [])

    def load_recipes(self) -> None:
        """Reload recipes from Excel."""
        self.recipes = self._load_recipes_from_excel()

    # ------------------------------------------------------------------
    # Dashboard 집계 위임 (PDCA #17)
    # ------------------------------------------------------------------

    def get_monthly_production_stats(self, months: int = 6) -> List[Dict]:
        """최근 N개월 월별 생산 통계."""
        return self.db_manager.get_monthly_production_stats(months=months)

    def get_top_materials(
        self,
        limit: int = 10,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict]:
        """기간 내 자재 사용량 TOP-N."""
        return self.db_manager.get_top_materials(
            limit=limit, start_date=start_date, end_date=end_date
        )

    def get_worker_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict]:
        """기간 내 작업자별 통계."""
        return self.db_manager.get_worker_stats(start_date=start_date, end_date=end_date)

    def get_recipe_frequency(
        self,
        limit: int = 10,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict]:
        """기간 내 레시피 실행 빈도 TOP-N."""
        return self.db_manager.get_recipe_frequency(
            limit=limit, start_date=start_date, end_date=end_date
        )

    # ------------------------------------------------------------------
    # 자재 재고 (PDCA #27 inventory_threshold_alert)
    # ------------------------------------------------------------------

    def get_all_material_stock(self) -> List[Dict]:
        """자재 재고 마스터 전체 조회."""
        return self.db_manager.get_all_material_stock()

    def upsert_material_stock(
        self,
        material_code: str,
        material_name: str,
        current_stock: float,
        min_stock_threshold: float,
        unit: str = "g",
    ) -> bool:
        """자재 재고/임계값 저장 (material_code 기준 upsert).

        DataManager 경로는 수동 편집 진입점(재고 설정 다이얼로그)이므로
        변경분을 ADJUST 이력으로 기록한다 (log_history=True, PDCA #34).
        """
        return self.db_manager.upsert_material_stock(
            material_code, material_name, current_stock, min_stock_threshold, unit,
            log_history=True
        )

    def seed_material_stock_from_history(self) -> int:
        """배합 이력의 자재를 재고 마스터에 0/0으로 시드. 신규 삽입 건수 반환."""
        return self.db_manager.seed_material_stock_from_history()

    def add_inbound(self, material_code: str, material_name: str, quantity: float,
                    unit: str = "g", note: str = "") -> bool:
        """입고(매입) 등록: 기존 재고에 수량을 누적 가산하고 이동 이력을 기록 (PDCA #30)."""
        return self.db_manager.add_inbound(material_code, material_name, quantity, unit, note)

    def get_stock_history(self, material_code: Optional[str] = None, limit: int = 200) -> List[Dict]:
        """자재 입출고 이력(최신순) 조회. material_code 지정 시 해당 자재만 (PDCA #30)."""
        return self.db_manager.get_stock_history(material_code, limit)

    def apply_replenishment(self, material_code: str, material_name: str, quantity: float,
                            unit: str = "g", note: str = "") -> bool:
        """재고 보충(입고)의 공개 별칭. add_inbound과 동일 동작 (PDCA #32 R3)."""
        return self.db_manager.apply_replenishment(material_code, material_name, quantity, unit, note)

    # ------------------------------------------------------------------
    # 자재 발주(PO) 관리 (PDCA #32 purchase_order_management)
    # ------------------------------------------------------------------

    def create_purchase_order(self, material_code: str, material_name: str, supplier: str,
                              ordered_qty: float, unit: str = "g",
                              note: str = "") -> Optional[int]:
        """발주 등록(상태 PENDING). 성공 시 발주 id, 실패 시 None."""
        return self.db_manager.create_purchase_order(
            material_code, material_name, supplier, ordered_qty, unit, note
        )

    def get_purchase_orders(self, status: Optional[str] = None, limit: int = 200) -> List[Dict]:
        """발주 목록(최신순) 조회. status 지정 시 해당 상태만. remaining_qty 포함."""
        return self.db_manager.get_purchase_orders(status, limit)

    def receive_purchase_order(self, po_id: int, received_qty: Optional[float] = None,
                               note: str = "") -> bool:
        """발주 입고 처리(부분/전체). 재고 누적 + INBOUND 이력 동일 트랜잭션."""
        return self.db_manager.receive_purchase_order(po_id, received_qty, note)

    def cancel_purchase_order(self, po_id: int) -> bool:
        """PENDING/PARTIAL 발주 취소(CANCELLED). 입고분 재고 원복 없음."""
        return self.db_manager.cancel_purchase_order(po_id)

    def get_inventory_alerts(self) -> List[MaterialAlert]:
        """현재 재고 기준 임계값 경고 목록(부족분 큰 순).

        전역 기본 임계값을 적용해 DB의 ``get_low_stock_materials`` SQL 경로와
        동일한 판정 결과를 보장한다(순수 함수 기반 프로그램 API).
        """
        rows = self.db_manager.get_all_material_stock()
        return evaluate_inventory_alerts(rows, default_threshold=self.get_default_min_threshold())

    def get_default_min_threshold(self) -> float:
        """전역 기본 최소 임계값(g). 자재별 임계값이 0일 때 적용."""
        try:
            return float(config.get("inventory_alert.default_min_threshold", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def set_default_min_threshold(self, value: float) -> bool:
        """전역 기본 최소 임계값을 설정에 저장."""
        try:
            amount = max(0.0, float(value or 0.0))
        except (TypeError, ValueError):
            amount = 0.0
        return config.set_value("inventory_alert.default_min_threshold", amount)

    def get_auto_deduct_on_save(self) -> bool:
        """배합 저장 시 재고 자동 차감 여부(기본 True)."""
        return bool(config.get("inventory_alert.auto_deduct_on_save", True))

    def set_auto_deduct_on_save(self, enabled: bool) -> bool:
        """배합 저장 시 재고 자동 차감 여부를 설정에 저장."""
        return config.set_value("inventory_alert.auto_deduct_on_save", bool(enabled))

    def get_low_stock_materials(self, default_threshold: Optional[float] = None) -> List[Dict]:
        """현재고가 (자재별 또는 전역 기본) 임계값 이하인 자재 목록.

        `default_threshold` 미지정 시 설정의 전역 기본 임계값을 사용한다.
        """
        if default_threshold is None:
            default_threshold = self.get_default_min_threshold()
        return self.db_manager.get_low_stock_materials(default_threshold=default_threshold)
