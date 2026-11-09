import os
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Soobin Swimwear E-Commerce"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+psycopg2://postgres:123456@localhost:5432/cnpm"
    )
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "soobin-swimwear-secret-key-super-secure-2026")
    SESSION_EXPIRE_HOURS: int = 72
    ACTION_TOKEN_EXPIRE_HOURS: int = 24
    
    # Shipping Mock Config
    MOCK_SHIPPING_FEE: float = 30000.0  # 30,000 VND
    CARRIER_NAME: str = "GHTK"
    
    # VietQR Bank Mock Info
    BANK_NAME: str = "MBBank (Ngân hàng Quân Đội)"
    BANK_ACCOUNT_NO: str = "0988123456"
    BANK_ACCOUNT_NAME: str = "CONG TY TNHH SOOBIN SWIMWEAR"
    
    model_config = ConfigDict(env_file=".env")

settings = Settings()
