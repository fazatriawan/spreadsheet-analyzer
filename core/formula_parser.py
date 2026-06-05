"""
Formula Parser: Parse formula -> identifikasi fungsi, referensi sel,
cross-sheet refs, hardcoded values, kompleksitas, warning.
"""
import re
from dataclasses import dataclass, field
from config import FORMULA_LOCALE
from utils.logger import get_logger

logger = get_logger(__name__)

FUNCTION_PATTERN = re.compile(r"([A-Z][A-Z0-9_]*)\s*\(")
RANGE_PATTERN = re.compile(r"(?:([A-Za-z0-9_]+)!)?\$?([A-Za-z]{1,3})\$?(\d+):\$?([A-Za-z]{1,3})\$?(\d+)")
CELL_PATTERN = re.compile(r"(?:([A-Za-z0-9_]+)!)?\$?([A-Za-z]{1,3})\$?(\d+)")
HARDCODED_PATTERN = re.compile(r"(?<![A-Za-z:!])\b(\d+\.?\d*)\b")

KNOWN_FUNCTIONS = {
    "SUM","SUMIF","SUMIFS","SUMPRODUCT","AVERAGE","AVERAGEIF","AVERAGEIFS",
    "COUNT","COUNTA","COUNTIF","COUNTIFS","MIN","MAX","ROUND","ROUNDUP",
    "ROUNDDOWN","ABS","MOD","POWER","SQRT","IF","IFS","AND","OR","NOT",
    "IFERROR","IFNA","SWITCH","VLOOKUP","HLOOKUP","INDEX","MATCH","OFFSET",
    "INDIRECT","XLOOKUP","XMATCH","CHOOSE","LOOKUP","CONCATENATE","CONCAT",
    "LEFT","RIGHT","MID","LEN","TRIM","UPPER","LOWER","TEXT","VALUE","SPLIT",
    "TODAY","NOW","DATE","YEAR","MONTH","DAY","DATEDIF","EDATE","EOMONTH",
    "NETWORKDAYS","WORKDAY","ARRAYFORMULA","QUERY","IMPORTRANGE","FILTER",
    "SORT","UNIQUE","TRANSPOSE","MMULT","FLATTEN","PMT","PV","FV","NPV","IRR",
}

@dataclass
class FormulaAnalysis:
    cell_address: str
    raw_formula: str
    is_formula: bool
    functions_used: list = field(default_factory=list)
    cell_references: list = field(default_factory=list)
    range_references: list = field(default_factory=list)
    cross_sheet_refs: list = field(default_factory=list)
    hardcoded_values: list = field(default_factory=list)
    complexity_score: int = 0
    formula_category: str = "unknown"
    description: str = ""
    warnings: list = field(default_factory=list)


def detect_locale_separator_issue(formula_body: str, locale: str = "indonesia") -> bool:
    """
    Deteksi pemisah argumen salah untuk locale Indonesia/Eropa.
    Locale ID: pemisah argumen = titik koma (;), bukan koma (,).
    Abaikan koma di dalam {array} atau string literal.
    """
    if locale.lower() not in ("indonesia", "id", "eu"):
        return False

    depth = 0
    brace = 0
    has_comma_arg = False
    has_semicolon_arg = False
    in_str, qc = False, None

    for ch in formula_body:
        if not in_str and ch in ('"', "'"):
            in_str, qc = True, ch
            continue
        if in_str:
            if ch == qc:
                in_str, qc = False, None
            continue

        if ch == "{":
            brace += 1
        elif ch == "}":
            brace = max(0, brace - 1)
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth > 0 and brace == 0:
            if ch == ",":
                has_comma_arg = True
            elif ch == ";":
                has_semicolon_arg = True

    return has_comma_arg and not has_semicolon_arg


class FormulaParser:
    def __init__(self, named_ranges=None):
        self.named_ranges = {nr["name"]: nr.get("range", "") for nr in (named_ranges or [])}

    def parse(self, addr: str, value: str) -> FormulaAnalysis:
        a = FormulaAnalysis(
            cell_address=addr, raw_formula=str(value),
            is_formula=str(value).startswith("=")
        )
        if not a.is_formula:
            return a
        f = str(value)[1:]
        a.functions_used = list(set(FUNCTION_PATTERN.findall(f.upper())) & KNOWN_FUNCTIONS)
        a.range_references = [
            {"sheet": m[1], "start": f"{m[2]}{m[3]}", "end": f"{m[4]}{m[5]}", "full": m.group(0)}
            for m in RANGE_PATTERN.finditer(f)
        ]
        used = {r["full"] for r in a.range_references}
        a.cell_references = [
            {"sheet": m[1], "col": m[2], "row": int(m[3]), "full": m.group(0)}
            for m in CELL_PATTERN.finditer(f) if m.group(0) not in used
        ]
        a.cross_sheet_refs = [r for r in a.cell_references + a.range_references if r.get("sheet")]
        a.hardcoded_values = HARDCODED_PATTERN.findall(f)
        a.complexity_score = (
            len(a.functions_used) * 2 + len(a.cell_references) +
            len(a.range_references) * 2 + len(a.cross_sheet_refs) * 3 +
            (5 if "ARRAYFORMULA" in a.functions_used else 0) +
            (4 if "INDIRECT" in a.functions_used else 0)
        )

        lookup = {"VLOOKUP","HLOOKUP","INDEX","MATCH","XLOOKUP","LOOKUP","IMPORTRANGE"}
        math_ = {"SUM","SUMIF","SUMIFS","SUMPRODUCT","AVERAGE","COUNT"}
        logic = {"IF","IFS","AND","OR","IFERROR","SWITCH"}
        array = {"ARRAYFORMULA","FILTER","SORT","UNIQUE","QUERY"}
        fset = set(a.functions_used)
        if fset & array:         a.formula_category = "array/query"
        elif fset & lookup:      a.formula_category = "lookup/reference"
        elif fset & logic:       a.formula_category = "logical"
        elif fset & math_:       a.formula_category = "math/aggregation"
        elif a.functions_used:   a.formula_category = "other"
        else:                    a.formula_category = "simple"

        if len(a.hardcoded_values) > 2:
            a.warnings.append("HARDCODED_VALUES: Banyak angka hardcoded, pertimbangkan referensi sel")
        if a.complexity_score > 15:
            a.warnings.append("HIGH_COMPLEXITY: Formula sangat kompleks, pertimbangkan dipecah")
        if "INDIRECT" in a.functions_used:
            a.warnings.append("VOLATILE_FUNCTION: INDIRECT memperlambat kalkulasi")

        if a.functions_used and detect_locale_separator_issue(f, FORMULA_LOCALE):
            a.warnings.append(
                "WRONG_SEPARATOR: Pemisah argumen memakai koma (,) — locale Indonesia harus titik koma (;)"
            )

        parts = []
        if a.functions_used:
            parts.append(f"Fungsi: {', '.join(a.functions_used)}")
        if a.cross_sheet_refs:
            sheets = set(r.get("sheet") for r in a.cross_sheet_refs if r.get("sheet"))
            parts.append(f"Cross-sheet: {', '.join(sheets)}")
        a.description = ". ".join(parts) or "Formula sederhana"
        return a

    def parse_sheet(self, sheet_data: dict, sheet_name: str) -> dict:
        results = {}
        for ri, row in enumerate(sheet_data.get("formulas", [])):
            for ci, val in enumerate(row):
                if val and str(val).startswith("="):
                    col = self._col_letter(ci)
                    addr = f"{sheet_name}!{col}{ri + 1}"
                    results[addr] = self.parse(addr, val)
        logger.info(f"  {len(results)} formula di '{sheet_name}'")
        return results

    @staticmethod
    def _col_letter(idx: int) -> str:
        r = ""
        while idx >= 0:
            r = chr(idx % 26 + ord('A')) + r
            idx = idx // 26 - 1
        return r
