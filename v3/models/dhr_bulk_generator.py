import random
from datetime import datetime, timedelta
from typing import List, Dict

from config.config_manager import config
from utils.logger import logger


class DhrBulkGenerator:
    def __init__(self, dhr_db, lot_manager):
        self.dhr_db = dhr_db
        self.lot_manager = lot_manager
        self.last_export_failures: List[str] = []

    def _validate_material_lots_for_date(self, work_date: str, materials: List[Dict]):
        missing = []
        lot_map = {}
        for m in materials:
            lots = self.lot_manager.get_lot(m["code"], work_date)
            if not lots:
                missing.append(m["code"])
                continue
            lot_value = lots[0][0] if isinstance(lots[0], tuple) else lots[0]
            lot_map[m["code"]] = lot_value
        return (len(missing) == 0), missing, lot_map

    def _get_base_time_for_date(self, product_name: str, work_date: str):
        records = self.dhr_db.get_dhr_records(start_date=work_date, end_date=work_date, limit=1000)
        latest = None
        for r in records:
            if r.get("product_name") != product_name:
                continue
            wt = (r.get("work_time") or "").strip()
            if not wt:
                continue
            try:
                t = datetime.strptime(wt, "%H:%M:%S").time()
                if latest is None or t > latest:
                    latest = t
            except ValueError:
                continue

        if latest:
            return datetime.strptime(f"{work_date} {latest.strftime('%H:%M:%S')}", "%Y-%m-%d %H:%M:%S")

        base_minute = random.randint(0, 59)
        return datetime.strptime(f"{work_date} 09:{base_minute:02d}:00", "%Y-%m-%d %H:%M:%S")

    def generate(self, entries: List[Dict], product_name: str, materials: List[Dict], worker: str,
                 include_time: bool, scan_effects: Dict, signature_options: Dict, export: bool = True) -> int:
        self.last_export_failures = []
        if not entries:
            return 0

        unique_dates = self._collect_unique_dates(entries)
        lot_map_by_date = self._build_lot_map_by_date(unique_dates, materials)

        last_time_by_date: Dict[str, datetime] = {}
        success_count = 0

        for entry in entries:
            work_date = entry["date"]
            amount = entry["amount"]
            work_time = self._resolve_work_time(product_name, work_date, last_time_by_date, include_time)
            product_lot = self.dhr_db.generate_product_lot(product_name, work_date)

            record_data, details_data = self._build_record_and_details(
                product_lot, product_name, worker, work_date, work_time, amount,
                materials, lot_map_by_date[work_date],
            )
            self.dhr_db.save_dhr_record(record_data, details_data)
            product_lot = record_data.get("product_lot", product_lot)

            if export:
                self._export_record(
                    product_lot=product_lot, product_name=product_name,
                    worker=worker, work_date=work_date, work_time=work_time,
                    include_time=include_time, amount=amount,
                    details_data=details_data, scan_effects=scan_effects,
                    signature_options=signature_options,
                )

            success_count += 1

        return success_count

    def _collect_unique_dates(self, entries: List[Dict]) -> List[str]:
        """Entry 목록에서 유일 날짜를 순서 보존하여 추출."""
        unique: List[str] = []
        for e in entries:
            if e["date"] not in unique:
                unique.append(e["date"])
        return unique

    def _build_lot_map_by_date(self, unique_dates: List[str], materials: List[Dict]) -> Dict[str, Dict[str, str]]:
        """날짜별 LOT 맵 빌드. 누락 자재 발견 시 ValueError raise."""
        lot_map_by_date: Dict[str, Dict[str, str]] = {}
        for d in unique_dates:
            ok, missing, lot_map = self._validate_material_lots_for_date(d, materials)
            if not ok:
                raise ValueError(f"{d} 날짜 LOT를 찾을 수 없는 자재가 있습니다. 해당 품목코드: {', '.join(missing)}")
            lot_map_by_date[d] = lot_map
        return lot_map_by_date

    def _resolve_work_time(self, product_name: str, work_date: str,
                           last_time_by_date: Dict[str, datetime], include_time: bool) -> str:
        """작업시간 계산. include_time=False면 "". 같은 날짜 2회차부터 +20~40분."""
        if not include_time:
            return ""
        if work_date not in last_time_by_date:
            last_time_by_date[work_date] = self._get_base_time_for_date(product_name, work_date)
        else:
            add_min = random.randint(20, 40)
            last_time_by_date[work_date] = last_time_by_date[work_date] + timedelta(minutes=add_min)
        return last_time_by_date[work_date].strftime("%H:%M:%S")

    def _build_record_and_details(self, product_lot: str, product_name: str, worker: str,
                                  work_date: str, work_time: str, amount: float,
                                  materials: List[Dict], lot_map: Dict[str, str]):
        """record_data와 details_data 빌드."""
        details_data = []
        for m in materials:
            ratio = m["ratio"]
            theory = amount * (ratio / 100.0)
            details_data.append({
                'material_code': m["code"],
                'material_name': m["name"],
                'material_lot': lot_map.get(m["code"], ""),
                'ratio': ratio,
                'theory_amount': theory,
                'actual_amount': theory,
            })
        record_data = {
            'product_lot': product_lot,
            'product_name': product_name,
            'worker': worker,
            'work_date': work_date,
            'work_time': work_time,
            'total_amount': amount,
            'scale': config.default_scale,
        }
        return record_data, details_data


    def _export_record(
        self,
        product_lot: str,
        product_name: str,
        worker: str,
        work_date: str,
        work_time: str,
        include_time: bool,
        amount: float,
        details_data: List[Dict],
        scan_effects: Dict,
        signature_options: Dict,
    ) -> None:
        signed_image_path = None
        image_to_embed = None
        try:
            from models.excel_exporter import ExcelExporter
            exporter = ExcelExporter()
            image_to_embed, signed_image_path = self._prepare_signed_image(worker, signature_options)
            export_data = self._build_bulk_export_data(
                product_lot, product_name, worker, work_date, work_time,
                include_time, amount, details_data,
            )
            self._run_bulk_export(exporter, export_data, image_to_embed, scan_effects, include_time)
        except Exception as e:
            msg = f"{product_lot}: {e}"
            self.last_export_failures.append(msg)
            logger.warning(f"DHR bulk export skipped after DB save ({msg})")
        finally:
            self._cleanup_signed_image(image_to_embed, signed_image_path)

    def _prepare_signed_image(self, worker: str, signature_options: Dict):
        """서명 이미지 생성. (image_to_embed, signed_image_path) 반환."""
        from models.image_processor import ImageProcessor
        import os
        base_dir = os.path.dirname(os.path.dirname(__file__))
        resources_path = os.path.join(base_dir, "resources", "signature")
        base_image_path = os.path.join(resources_path, "image.jpeg")

        signature_cfg = config.get("signature", {})
        if signature_options:
            signature_cfg["include"] = signature_options

        img_processor = ImageProcessor(resources_path=resources_path, config=signature_cfg)
        signed_image_path = os.path.join(base_dir, "resources", f"temp_signed_{worker}.png")

        image_to_embed = None
        if os.path.exists(base_image_path):
            success, _ = img_processor.create_signed_image(base_image_path, signed_image_path, worker)
            image_to_embed = signed_image_path if success else base_image_path
        return image_to_embed, signed_image_path

    def _build_bulk_export_data(self, product_lot: str, product_name: str, worker: str,
                                work_date: str, work_time: str, include_time: bool,
                                amount: float, details_data: List[Dict]) -> Dict:
        """export_data dict 빌드 (이미지/효과는 별도 인자)."""
        return {
            "product_lot": product_lot,
            "recipe_name": product_name,
            "worker": worker,
            "work_date": work_date,
            "work_time": work_time if include_time else "",
            "total_amount": amount,
            "scale": config.default_scale,
            "materials": details_data,
        }

    def _run_bulk_export(self, exporter, export_data: Dict, image_to_embed,
                         scan_effects: Dict, include_time: bool):
        """Excel + PDF 실행. 각 실패 시 RuntimeError raise."""
        excel_path = exporter.export_to_excel(
            export_data,
            include_image=bool(image_to_embed),
            image_path=image_to_embed,
            include_work_time=include_time,
        )
        if not excel_path:
            raise RuntimeError("Excel export failed")
        pdf_path = exporter.export_to_pdf(excel_path, scan_effects or {})
        if not pdf_path:
            raise RuntimeError("PDF export failed")
        return excel_path, pdf_path

    def _cleanup_signed_image(self, image_to_embed, signed_image_path) -> None:
        """signed_image가 사용됐다면 삭제 시도."""
        import os
        if image_to_embed == signed_image_path and signed_image_path and os.path.exists(signed_image_path):
            try:
                os.remove(signed_image_path)
            except OSError:
                pass
