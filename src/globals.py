from fastapi.security import OAuth2PasswordBearer
import IP2Location


# Yanille uses the IP2Location LITE database for <a href="https://lite.ip2location.com">IP geolocation</a>.


class Globals:
    
    oauth2_admin_scheme = OAuth2PasswordBearer(tokenUrl="/admin/admin-login")    
    geoip_reader = IP2Location.IP2Location("res/IP2LOCATION-LITE-DB1.BIN")