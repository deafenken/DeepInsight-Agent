from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "enterprise_analysis.db"
CHROMA_DIR = DATA_DIR / "chroma"
RAW_MACRO_DIR = DATA_DIR / "raw_macro"
ARCHIVE_DIR = DATA_DIR / "archives"
DEMO_CACHE_DIR = ROOT_DIR / "demo_cache"
REPORTS_DIR = ROOT_DIR / "reports_md"
ALT_REPORTS_DIR = ROOT_DIR / "report_md"
FINAL_REPORTS_DIR = ROOT_DIR / "Final_md"
ASSETS_DIR = ROOT_DIR / "assets"
IMAGES_DIR = ASSETS_DIR / "images"
REFERENCE_MOLECULE_IMAGE = IMAGES_DIR / "reference_molecule.png"
DEFAULT_MACRO_SAMPLE = RAW_MACRO_DIR / "国家统计局_卫生_2022_2024.xlsx"
