from __future__ import annotations

from typing import List, Tuple

import pandas as pd
from datetime import datetime

from utils.logger import logger


class LotManager:
    def __init__(self, excel_path):
        """
        Initializes the LotManager by loading the lot data from the specified Excel file.
        """
        self.excel_path = excel_path
        self.df = None
        self.load_data()

    def load_data(self):
        """
        Loads data from the Excel file into a pandas DataFrame.
        The 'Lot.No' and '품목코드' columns are treated as strings.
        """
        try:
            # Specify dtype to ensure LOT numbers and item codes are treated as strings
            self.df = pd.read_excel(
                self.excel_path,
                dtype={'Lot.No': str, '품목코드': str}
            )
            # Convert date column to datetime objects for comparison
            # Assuming the first column is the date column.
            date_column_name = self.df.columns[0]
            self.df[date_column_name] = pd.to_datetime(self.df[date_column_name])
        except FileNotFoundError:
            # Handle case where the Excel file doesn't exist
            logger.warning(f"LOT 데이터 파일을 찾을 수 없습니다: {self.excel_path}")
            self.df = pd.DataFrame()
        except (OSError, ValueError, KeyError) as e:
            # Handle other potential errors during file loading
            logger.error(f"LOT 데이터 로드 중 오류 발생 ({self.excel_path}): {e}", exc_info=True)
            self.df = pd.DataFrame()

    def get_lot(self, item_code: str, work_date: str) -> List[Tuple[str, str]]:
        """
        Finds the oldest LOT number(s) with a shipment date on or after the given work date.

        Args:
            item_code: The item code to search for.
            work_date: The reference work date in 'YYYY-MM-DD' format.

        Returns:
            A list of unique (LOT number, shipment date) tuples.
            Returns an empty list if no suitable LOT is found.
        """
        logger.debug(f"--- 로트 추적 시작: 품목코드={item_code}, 작업일자={work_date} ---")

        if self.df.empty:
            logger.warning("로트 데이터프레임이 비어있습니다. OUT.xlsx 파일을 확인하세요.")
            return []

        try:
            work_datetime = datetime.strptime(work_date, "%Y-%m-%d")
            date_column_name = self.df.columns[0]

            # 1. 품목코드로 필터링
            item_df = self.df[self.df['품목코드'] == item_code].copy()
            logger.debug(f"1. 품목코드 '{item_code}' 필터링 결과: {len(item_df)}건")
            if item_df.empty:
                logger.warning(f"'{item_code}'에 해당하는 품목이 OUT.xlsx에 없습니다.")
                return []

            # 상세 로깅
            logger.debug(f"  - 비교 기준 작업일자 (datetime): {work_datetime}")
            if not item_df.empty:
                log_df = item_df[[date_column_name, 'Lot.No']].dropna(subset=['Lot.No'])
                logger.debug(f"  - '{item_code}'에 대한 전체 출고 데이터:\n{log_df.to_string()}")

            # 2. 작업일자 이후 출고건으로 필터링
            relevant_dates_df = item_df[item_df[date_column_name] >= work_datetime]
            logger.debug(f"2. 작업일자 '{work_date}' 이후 출고 건 필터링 결과: {len(relevant_dates_df)}건")
            if relevant_dates_df.empty:
                logger.warning(f"'{item_code}'의 작업일자 이후 출고 기록이 없습니다.")
                return []

            # 3. 가장 가까운 미래 출고일자 찾기
            closest_future_date = relevant_dates_df[date_column_name].min()
            closest_future_date_str = closest_future_date.strftime('%Y-%m-%d')
            logger.debug(f"3. 가장 가까운 출고일자: {closest_future_date_str}")

            # 4. 해당 날짜의 모든 기록 가져오기
            final_lots_df = relevant_dates_df[relevant_dates_df[date_column_name] == closest_future_date]

            # 5. 고유 로트번호 목록 생성
            lots = final_lots_df['Lot.No'].unique().tolist()
            logger.debug(f"4. 최종 후보 로트: {lots}")

            # 6. (로트, 날짜) 튜플 목록 생성 및 반환
            result = [(lot, closest_future_date_str) for lot in lots]
            logger.debug(f"--- 로트 추적 종료: 최종 반환={result} ---")
            return result

        except (ValueError, KeyError, TypeError) as e:
            logger.error(f"로트 추적 중 오류 발생 (품목코드: {item_code}): {e}", exc_info=True)
            return []
