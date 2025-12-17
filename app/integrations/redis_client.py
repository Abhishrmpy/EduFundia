import redis
import json
import pickle
from typing import Optional, Any, Union, List, Dict
from datetime import timedelta
import logging
from ..core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client for caching and session management"""
    
    def __init__(self):
        self.client = None
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis connection"""
        try:
            self.client = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                max_connections=50
            )
            
            # Test connection
            self.client.ping()
            logger.info("Redis connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None
    
    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        if not self.client:
            return False
        
        try:
            self.client.ping()
            return True
        except:
            return False
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis"""
        if not self.is_connected():
            return None
        
        try:
            value = self.client.get(key)
            if value:
                # Try to decode as JSON first, then as pickle
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    try:
                        return pickle.loads(value.encode('latin1'))
                    except:
                        return value
            return None
        except Exception as e:
            logger.error(f"Error getting key {key} from Redis: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None
    ) -> bool:
        """Set value in Redis"""
        if not self.is_connected():
            return False
        
        try:
            if expire is None:
                expire = settings.redis_cache_ttl
            
            # Try to encode as JSON first
            try:
                serialized = json.dumps(value)
            except (TypeError, OverflowError):
                # Fallback to pickle for complex objects
                serialized = pickle.dumps(value).decode('latin1')
            
            if expire > 0:
                self.client.setex(key, expire, serialized)
            else:
                self.client.set(key, serialized)
            
            return True
        except Exception as e:
            logger.error(f"Error setting key {key} in Redis: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis"""
        if not self.is_connected():
            return False
        
        try:
            result = self.client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Error deleting key {key} from Redis: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis"""
        if not self.is_connected():
            return False
        
        try:
            return self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Error checking key {key} in Redis: {e}")
            return False
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration for a key"""
        if not self.is_connected():
            return False
        
        try:
            return self.client.expire(key, seconds)
        except Exception as e:
            logger.error(f"Error setting expiration for key {key}: {e}")
            return False
    
    async def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment counter"""
        if not self.is_connected():
            return None
        
        try:
            return self.client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Error incrementing key {key}: {e}")
            return None
    
    async def decr(self, key: str, amount: int = 1) -> Optional[int]:
        """Decrement counter"""
        if not self.is_connected():
            return None
        
        try:
            return self.client.decrby(key, amount)
        except Exception as e:
            logger.error(f"Error decrementing key {key}: {e}")
            return None
    
    async def hset(self, key: str, field: str, value: Any) -> bool:
        """Set hash field"""
        if not self.is_connected():
            return False
        
        try:
            # Try to encode as JSON
            try:
                serialized = json.dumps(value)
            except (TypeError, OverflowError):
                serialized = str(value)
            
            return self.client.hset(key, field, serialized) > 0
        except Exception as e:
            logger.error(f"Error setting hash field {field} for key {key}: {e}")
            return False
    
    async def hget(self, key: str, field: str) -> Optional[Any]:
        """Get hash field"""
        if not self.is_connected():
            return None
        
        try:
            value = self.client.hget(key, field)
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return None
        except Exception as e:
            logger.error(f"Error getting hash field {field} for key {key}: {e}")
            return None
    
    async def hgetall(self, key: str) -> Dict[str, Any]:
        """Get all hash fields"""
        if not self.is_connected():
            return {}
        
        try:
            result = self.client.hgetall(key)
            decoded = {}
            for k, v in result.items():
                try:
                    decoded[k] = json.loads(v)
                except json.JSONDecodeError:
                    decoded[k] = v
            return decoded
        except Exception as e:
            logger.error(f"Error getting all hash fields for key {key}: {e}")
            return {}
    
    async def sadd(self, key: str, *values: Any) -> bool:
        """Add to set"""
        if not self.is_connected():
            return False
        
        try:
            serialized_values = [str(v) for v in values]
            return self.client.sadd(key, *serialized_values) > 0
        except Exception as e:
            logger.error(f"Error adding to set {key}: {e}")
            return False
    
    async def smembers(self, key: str) -> List[str]:
        """Get set members"""
        if not self.is_connected():
            return []
        
        try:
            return list(self.client.smembers(key))
        except Exception as e:
            logger.error(f"Error getting set members for key {key}: {e}")
            return []
    
    async def lpush(self, key: str, *values: Any) -> bool:
        """Push to list (left)"""
        if not self.is_connected():
            return False
        
        try:
            serialized_values = [str(v) for v in values]
            return self.client.lpush(key, *serialized_values) > 0
        except Exception as e:
            logger.error(f"Error pushing to list {key}: {e}")
            return False
    
    async def lrange(self, key: str, start: int = 0, end: int = -1) -> List[str]:
        """Get list range"""
        if not self.is_connected():
            return []
        
        try:
            return self.client.lrange(key, start, end)
        except Exception as e:
            logger.error(f"Error getting list range for key {key}: {e}")
            return []
    
    async def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern"""
        if not self.is_connected():
            return []
        
        try:
            return self.client.keys(pattern)
        except Exception as e:
            logger.error(f"Error getting keys for pattern {pattern}: {e}")
            return []
    
    async def flushdb(self) -> bool:
        """Flush Redis database"""
        if not self.is_connected():
            return False
        
        try:
            self.client.flushdb()
            logger.info("Redis database flushed")
            return True
        except Exception as e:
            logger.error(f"Error flushing Redis database: {e}")
            return False
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get Redis cache statistics"""
        if not self.is_connected():
            return {"connected": False}
        
        try:
            info = self.client.info()
            stats = {
                "connected": True,
                "used_memory": info.get("used_memory_human", "0"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0),
            }
            
            # Calculate hit rate
            hits = stats["keyspace_hits"]
            misses = stats["keyspace_misses"]
            total = hits + misses
            stats["hit_rate"] = (hits / total * 100) if total > 0 else 0
            
            return stats
        except Exception as e:
            logger.error(f"Error getting Redis stats: {e}")
            return {"connected": False, "error": str(e)}


# Singleton instance
redis_client = RedisClient()