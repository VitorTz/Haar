from dotenv import load_dotenv
import ipaddress
import os


load_dotenv()


class Constants:

    API_NAME = "Yanille - URL Shortener"
    API_DESCR = "URL Shortener"
    API_VERSION = "1.0.0"    

    MAX_REQUESTS = 200
    WINDOW = 30
    
    IS_PRODUCTION = os.getenv("ENV", "DEV") == "PROD"
    SENSITIVE_PATHS = ["/auth/", "/admin/"]

    CONTENT_SECURITY_HEADER = (
        "default-src 'self'; "
        "script-src 'self' https://cdnjs.cloudflare.com; "
        "style-src 'self' https://cdnjs.cloudflare.com 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' https://cdnjs.cloudflare.com; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
    PERMISSIONS_POLICY_HEADER = (
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "gyroscope=(), "
        "accelerometer=()"
    )

    SECRET_KEY = os.getenv("SECRET_KEY")
    ALGORITHM = os.getenv("ALGORITHM")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
    
    MAX_BODY_SIZE = 20 * 1024 * 1024
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    ACCESS_TOKEN_EXPIRE_HOURS = 2

    MAX_FAILED_ATTEMPTS = 10
    LOCK_TIME_MINUTES = 16
    CACHE_EXPIRE_SECONDS = 60

    SAFE_BROWSING_URL = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={os.getenv('GOOGLE_SAFE_BROWSING_API_KEY')}"

    SAFE_CACHE_TTL=21600 # 6 hours

    PRIVATE_NETWORKS = [
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("::1/128"),
        ipaddress.ip_network("fc00::/7"),
    ]

    DEBUG_MODE = str(os.getenv("DEBUG_MODE", '0')).strip() == '1'