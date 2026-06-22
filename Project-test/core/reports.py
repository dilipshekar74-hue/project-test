from __future__ import annotations

from io import BytesIO

import pandas as pd


def build_excel_report(sheets: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, frame in sheets.items():
            safe_name = sheet_name[:31] if sheet_name else "Sheet1"
            frame.to_excel(writer, sheet_name=safe_name, index=False)
    return buffer.getvalue()
from __future__ import annotations

from io import BytesIO

import pandas as pd


def build_excel_report(sheets: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, frame in sheets.items():
            safe_name = sheet_name[:31] if sheet_name else "Sheet1"
            frame.to_excel(writer, sheet_name=safe_name, index=False)
    return buffer.getvalue()
