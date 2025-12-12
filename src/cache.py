import time
import pickle
from threading import RLock


class RedisLikeCache:
    _instance = None
    _lock = RLock()

    MAX_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_cache()
            return cls._instance

    def _init_cache(self):
        self.cache = {}
        self.current_size = 0
        self.counter = 0

    def _cleanup_expired(self):
        now = time.time()
        expired_keys = [k for k, v in self.cache.items() if v["expires"] < now]
        for k in expired_keys:
            self._evict_key(k)

    def _evict_key(self, key):
        entry = self.cache.pop(key, None)
        if entry:
            self.current_size -= entry["size"]

    def _evict_oldest_until_fit(self):
        # Sorted by insertion order (ts)
        while self.current_size > self.MAX_SIZE_BYTES and self.cache:
            oldest_key = min(self.cache.items(), key=lambda kv: kv[1]["ts"])[0]
            self._evict_key(oldest_key)

    def set(self, key, value, ttl_seconds):
        with self._lock:
            self._cleanup_expired()

            expires = time.time() + ttl_seconds
            serialized = pickle.dumps(value)
            size = len(serialized)
            self.counter += 1
            
            if key in self.cache:
                self._evict_key(key)
            
            self.cache[key] = {
                "value": serialized,
                "expires": expires,
                "size": size,
                "ts": self.counter
            }
            self.current_size += size            
            self._evict_oldest_until_fit()

    def get(self, key):
        with self._lock:
            self._cleanup_expired()

            entry = self.cache.get(key)
            if not entry:
                return None

            if entry["expires"] < time.time():
                self._evict_key(key)
                return None

            return pickle.loads(entry["value"])
