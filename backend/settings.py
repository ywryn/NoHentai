import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
DATA_DIR = Path(os.getenv('NOHENTAI_DATA_DIR', ROOT / 'var')).resolve()
DB_PATH = DATA_DIR / 'nohentai.sqlite3'
SECRET_NAMES = (
    'EXHENTAI_BASE_URL', 'EXHENTAI_COOKIE_MEMBER_ID', 'EXHENTAI_COOKIE_PASS_HASH',
    'EXHENTAI_COOKIE_IGNEOUS', 'LLM_API_KEY', 'LLM_API_BASE', 'LLM_MODEL',
    'LLM_JSON_MODE', 'GOOGLE_VISION_API_KEY', 'PADDLEOCR_API_TOKEN', 'OCR_SPACE_KEY', 'TRANS_PASSWORD',
)


def encryption_key():
    key = os.getenv('CREDENTIAL_ENCRYPTION_KEY', '')
    if not key:
        raise RuntimeError('请配置 CREDENTIAL_ENCRYPTION_KEY（参见部署文档）')
    return key.encode()


def origins():
    return [v.strip().rstrip('/') for v in os.getenv(
        'ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',') if v.strip()]
