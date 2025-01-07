import logging
import functools
from datetime import datetime
import time
from typing import Callable, Any

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s', 
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def async_error_handler(func: Callable) -> Callable:
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            logging.info(f"{func.__name__} completed in {elapsed:.3f}s")
            return result
        except Exception as e:
            logging.error(f"Error in {func.__name__}: {str(e)}")
            raise
    return wrapper