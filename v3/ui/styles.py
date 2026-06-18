"""UI 스타일 및 테마 상수 정의 (Fluent-compatible)."""


class UITheme:
    """중앙화된 UI 테마 상수 - 프리미엄 다크 스타일"""
    
    # 메인 색상 (Deep Dark)
    BACKGROUND_PRIMARY = "#0C0F14"  # 전체 배경 (가장 어두움)
    BACKGROUND_GRADIENT_END = "#10151F"
    SURFACE_DARK = "#10141B"        # 카드 배경 1
    SURFACE_ALT = "#141A23"         # 카드 배경 2 (약간 밝음)
    
    # 포인트 색상 (Amber Gradient)
    MINT_ACCENT = "#E3A12F"
    MINT_GRADIENT_START = "#F2C066"
    MINT_GRADIENT_END = "#D9901E"
    MINT_HOVER_START = "#FFD07A"
    MINT_HOVER_END = "#E3A12F"
    
    TEXT_PRIMARY = "#F5F7FA"
    TEXT_SECONDARY = "#C2CAD8"  # 연한 회색 (가독성 개선)
    TEXT_ON_ACCENT = "#1A1206"
    TEXT_PLACEHOLDER = "#D5DBE6"

    # Accent alpha helpers
    ACCENT_RGBA_08 = "rgba(227, 161, 47, 0.08)"
    ACCENT_RGBA_12 = "rgba(227, 161, 47, 0.12)"
    ACCENT_RGBA_16 = "rgba(227, 161, 47, 0.16)"
    ACCENT_RGBA_18 = "rgba(227, 161, 47, 0.18)"
    ACCENT_RGBA_22 = "rgba(227, 161, 47, 0.22)"
    ERROR_BG = "rgba(255, 77, 79, 0.2)"
    READONLY_BG = "#1C222D"
    ACCENT_HIGHLIGHT_BG = "#2A2212"
    ERROR_HIGHLIGHT_BG = "#3A1C1C"
    FIELD_BG = "rgba(255, 255, 255, 0.08)"
    FIELD_BG_HOVER = "rgba(255, 255, 255, 0.12)"
    FIELD_BG_PRESSED = "rgba(255, 255, 255, 0.16)"
    BORDER_LIGHT = "rgba(255, 255, 255, 0.18)"
    BORDER_SUBTLE = "rgba(255, 255, 255, 0.06)"
    BORDER_SUBTLE_LIGHT = "rgba(255, 255, 255, 0.04)"
    ACCENT_BORDER = "rgba(227, 161, 47, 0.35)"
    SCROLLBAR_HANDLE_BG = "rgba(255, 255, 255, 0.15)"
    ERROR_BG_LIGHT = "rgba(239, 68, 68, 0.1)"
    ERROR_BG_STRONG = "rgba(239, 68, 68, 0.2)"
    
    # 상태 색상
    SUCCESS_COLOR = "#2ECC71"
    WARNING_COLOR = "#F5A623"
    ERROR_COLOR = "#FF4D4F"
    
    # 테두리 및 배경
    BORDER_COLOR = "rgba(255, 255, 255, 0.08)"
    BORDER_ACCENT = "rgba(227, 161, 47, 0.2)"
    
    # 폰트 (SSOT — main.py setFontFamilies와 정렬, 한글 미지원 Bahnschrift 제거)
    FONT_FAMILY = "'Pretendard', 'Segoe UI', 'Malgun Gothic', 'Noto Sans KR', sans-serif"

    # 크기
    DEFAULT_WINDOW_WIDTH = 1200
    DEFAULT_WINDOW_HEIGHT = 800
    CARD_BORDER_RADIUS = 14
    BUTTON_BORDER_RADIUS = 8


class UIStyles:
    """재사용 가능한 스타일시트 - 프리미엄 스타일 (SSOT)"""
    
    @staticmethod
    def get_base_style():
        """기본 위젯 및 폰트 설정"""
        return f"""
        /* 전역 폰트 설정 */
        QLabel, QPushButton, QLineEdit, QComboBox, QTableWidget, QTextEdit, QPlainTextEdit {{
            font-family: {UITheme.FONT_FAMILY};
            font-size: 14px;
        }}

        /* 기본 라벨 색상 */
        QLabel {{
            color: {UITheme.TEXT_PRIMARY};
        }}

        QGroupBox::title {{
            color: {UITheme.TEXT_SECONDARY};
        }}

        QGroupBox {{
            color: {UITheme.TEXT_PRIMARY};
            background-color: {UITheme.SURFACE_ALT};
            border: 1px solid {UITheme.BORDER_SUBTLE};
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 6px;
        }}

        CardWidget {{
            background-color: {UITheme.SURFACE_ALT};
            border-radius: {UITheme.CARD_BORDER_RADIUS}px;
            border: 1px solid {UITheme.BORDER_SUBTLE};
        }}

        QWidget#DHRContent {{
            background-color: {UITheme.BACKGROUND_PRIMARY};
        }}

        QMessageBox {{
            background-color: #F5F7FA;
        }}
        QMessageBox QLabel {{
            color: #111111;
        }}
        QMessageBox QPushButton, QMessageBox QAbstractButton {{
            color: #111111;
        }}

        QTabWidget::pane {{
            border: 1px solid {UITheme.BORDER_SUBTLE};
            background-color: {UITheme.SURFACE_ALT};
            border-radius: 8px;
        }}
        QTabBar::tab {{
            background-color: {UITheme.SURFACE_DARK};
            color: {UITheme.TEXT_SECONDARY};
            padding: 8px 16px;
            border: 1px solid {UITheme.BORDER_SUBTLE};
            border-bottom: none;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            margin-right: 4px;
        }}
        QTabBar::tab:selected {{
            background-color: {UITheme.SURFACE_ALT};
            color: {UITheme.TEXT_PRIMARY};
            border-bottom: 1px solid {UITheme.SURFACE_ALT};
        }}
        QTabBar::tab:!selected {{
            margin-top: 2px;
        }}

        /* 윈도우 및 메인 패널 배경 */
        QMainWindow, QWidget#MixingPage, QWidget#DashboardPage, QWidget#SettingsPage {{
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {UITheme.BACKGROUND_PRIMARY}, stop:1 {UITheme.BACKGROUND_GRADIENT_END});
        }}
        """

    @staticmethod
    def get_navigation_style():
        """사이드바 (NavigationInterface) 스타일"""
        return f"""
        NavigationInterface, NavigationPanel {{
            background-color: {UITheme.BACKGROUND_PRIMARY};
            border: none;
        }}
        NavigationInterface QToolButton {{
            border-radius: 4px;
            color: {UITheme.TEXT_SECONDARY};
            font-size: 14px;
            padding: 8px;
            margin: 2px 4px;
            background-color: transparent;
            border: none;
        }}
        NavigationInterface QToolButton:hover {{
            background-color: {UITheme.ACCENT_RGBA_12};
            color: {UITheme.TEXT_PRIMARY};
        }}
        NavigationInterface QToolButton:checked {{
            background-color: {UITheme.ACCENT_RGBA_18};
            color: {UITheme.MINT_ACCENT};
            font-weight: bold;
            border-left: 3px solid {UITheme.MINT_ACCENT};
        }}
        """

    @staticmethod
    def get_input_style():
        """입력 필드 (ComboBox, LineEdit, SpinBox) 스타일"""
        return f"""
        /* 콤보박스 */
        QComboBox {{
            background-color: {UITheme.FIELD_BG};
            color: {UITheme.TEXT_PRIMARY};
            border: 1px solid {UITheme.BORDER_COLOR};
            border-radius: {UITheme.BUTTON_BORDER_RADIUS}px;
            padding: 8px 12px;
        }}
        QComboBox QLineEdit {{
            color: {UITheme.TEXT_PRIMARY};
        }}
        QComboBox:hover {{
            background-color: {UITheme.FIELD_BG_HOVER};
        }}
        QComboBox:focus {{
            border: 1px solid {UITheme.MINT_ACCENT};
            background-color: {UITheme.ACCENT_RGBA_08};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {UITheme.SURFACE_ALT};
            color: {UITheme.TEXT_PRIMARY};
            border: 1px solid {UITheme.BORDER_COLOR};
            selection-background-color: {UITheme.ACCENT_RGBA_18};
            outline: none;
        }}
        
        /* 입력 필드 공통 */
        QLineEdit, QSpinBox, QDoubleSpinBox {{
            background-color: {UITheme.FIELD_BG};
            border: 1px solid {UITheme.BORDER_LIGHT};
            border-radius: 6px;
            padding: 10px 14px;
            color: {UITheme.TEXT_PRIMARY};
            selection-background-color: {UITheme.MINT_ACCENT};
            selection-color: {UITheme.TEXT_ON_ACCENT};
        }}
        QLineEdit::placeholder {{
            color: {UITheme.TEXT_PLACEHOLDER};
        }}
        QComboBox QLineEdit::placeholder {{
            color: {UITheme.TEXT_PLACEHOLDER};
        }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 1px solid {UITheme.MINT_ACCENT};
            background-color: {UITheme.ACCENT_RGBA_08};
        }}
        """

    @staticmethod
    def get_scrollbar_style():
        """스크롤바 스타일"""
        return f"""
        QScrollBar:vertical {{
            width: 8px;
            background: transparent;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {UITheme.SCROLLBAR_HANDLE_BG};
            border-radius: 4px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {UITheme.MINT_ACCENT};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        """

    @staticmethod
    def get_main_style():
        """전체 글로벌 스타일 통합 반환"""
        return (
            UIStyles.get_base_style() +
            UIStyles.get_navigation_style() +
            UIStyles.get_input_style() +
            UIStyles.get_scrollbar_style()
        )

    @staticmethod
    def get_primary_button_style():
        """Primary (Gradient) 버튼 스타일"""
        return f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {UITheme.MINT_GRADIENT_START}, stop:1 {UITheme.MINT_GRADIENT_END});
            color: {UITheme.TEXT_ON_ACCENT};
            border: none;
            border-radius: {UITheme.BUTTON_BORDER_RADIUS}px;
            font-weight: 700;
            padding: 10px 18px;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {UITheme.MINT_HOVER_START}, stop:1 {UITheme.MINT_HOVER_END});
        }}
        QPushButton:pressed {{
            background: {UITheme.MINT_GRADIENT_END};
        }}
        QPushButton:disabled {{
            background: {UITheme.ACCENT_RGBA_18};
            color: {UITheme.TEXT_PRIMARY};
            border: 1px solid {UITheme.ACCENT_BORDER};
        }}
        """

    @staticmethod
    def get_secondary_button_style():
        """Secondary (Outline/Ghost) 버튼 스타일"""
        return f"""
        QPushButton {{
            background-color: transparent;
            color: {UITheme.TEXT_SECONDARY};
            border: 1px solid {UITheme.BORDER_COLOR};
            border-radius: {UITheme.BUTTON_BORDER_RADIUS}px;
            padding: 10px 18px;
            font-size: 13px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {UITheme.FIELD_BG};
            color: {UITheme.TEXT_PRIMARY};
            border: 1px solid {UITheme.TEXT_SECONDARY};
        }}
        QPushButton:pressed {{
            background-color: {UITheme.FIELD_BG_PRESSED};
        }}
        """
        
    @staticmethod
    def get_danger_button_style():
        """Danger (Red Outline) 버튼 스타일"""
        return f"""
        QPushButton {{
            background-color: transparent;
            color: {UITheme.ERROR_COLOR};
            border: 1px solid {UITheme.ERROR_COLOR};
            border-radius: {UITheme.BUTTON_BORDER_RADIUS}px;
            padding: 10px 18px;
            font-size: 13px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {UITheme.ERROR_BG_LIGHT};
        }}
        QPushButton:pressed {{
            background-color: {UITheme.ERROR_BG_STRONG};
        }}
        """

    @staticmethod
    def get_card_style():
        """카드 위젯 공통 스타일"""
        return f"""
        QWidget {{
            background-color: {UITheme.SURFACE_ALT};
            border-radius: {UITheme.CARD_BORDER_RADIUS}px;
            border: 1px solid {UITheme.BORDER_SUBTLE};
        }}
        """

    @staticmethod
    def get_table_style():
        """테이블 위젯 스타일"""
        return f"""
        QTableWidget {{
            background-color: {UITheme.SURFACE_ALT};
            gridline-color: {UITheme.BORDER_COLOR};
            color: {UITheme.TEXT_PRIMARY};
            border: none;
            border-radius: 8px;
            selection-background-color: {UITheme.ACCENT_RGBA_16};
            selection-color: {UITheme.TEXT_PRIMARY};
        }}
        QHeaderView::section {{
            background-color: {UITheme.SURFACE_DARK};
            color: {UITheme.MINT_ACCENT};
            border: none;
            border-bottom: 2px solid {UITheme.MINT_ACCENT};
            padding: 8px;
            font-weight: bold;
        }}
        QTableCornerButton::section {{
            background-color: {UITheme.SURFACE_DARK};
            border: none;
        }}
        QTableWidget::item {{
            padding: 12px 10px;
            border-bottom: 1px solid {UITheme.BORDER_SUBTLE_LIGHT};
        }}
        QTableWidget::item:selected {{
            background-color: {UITheme.ACCENT_RGBA_22};
            color: {UITheme.MINT_ACCENT};
        }}
        QTableWidget::item:hover {{
            background-color: {UITheme.ACCENT_RGBA_12};
        }}
        """

    @staticmethod
    def get_dialog_style():
        """모달 다이얼로그 (프레임리스) 스타일"""
        return f"""
        QDialog {{
            background-color: {UITheme.BACKGROUND_PRIMARY};
            border: 1px solid {UITheme.BORDER_COLOR};
            border-radius: 16px;
        }}
        """


# 하위 호환성 유지
def get_main_style():
    return UIStyles.get_main_style()
