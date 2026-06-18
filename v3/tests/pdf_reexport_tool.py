import argparse
import asyncio

from models.data_manager import DataManager
from config.config_manager import config


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regenerate PDF for an existing record.")
    parser.add_argument("--lot", default="CSPB25102401", help="Product LOT number")
    parser.add_argument("--timeout", type=float, default=30.0, help="Timeout seconds for PDF generation")
    parser.add_argument("--skip-export", action="store_true", help="Skip PDF export (fast check)")
    return parser.parse_args()


async def _export_with_timeout(
    data_manager: DataManager,
    product_lot: str,
    effects_params: dict,
    timeout_sec: float,
):
    return await asyncio.wait_for(
        asyncio.to_thread(data_manager.export_existing_record, product_lot, effects_params),
        timeout=timeout_sec,
    )


async def main():
    """
    Temporary script to regenerate a PDF for an existing record.
    """
    print("PDF 재출력 기능을 시작합니다...")
    data_manager = DataManager()

    # Get default scan effects from config
    effects_params = config.scan_effects

    args = _parse_args()
    product_lot = args.lot

    print(f"LOT: {product_lot}에 대한 PDF를 재생성합니다.")
    print(f"스캔 효과 설정 파라미터: {effects_params}")

    if args.skip_export:
        print("건너뜀: PDF 재출력 생략 (--skip-export)")
        return

    # Regenerate the PDF (with timeout)
    pdf_file = await _export_with_timeout(data_manager, product_lot, effects_params, args.timeout)

    if pdf_file:
        print(f"성공: PDF가 아래 경로에 생성되었습니다: {pdf_file}")
    else:
        print("실패: PDF 파일이 생성되지 않았습니다.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except asyncio.TimeoutError:
        print("시간초과: PDF 재생성이 제한 시간 내 완료되지 못했습니다.")
    except Exception as e:
        print(f"예기치 않은 오류가 발생: {e}")
