import logging

def calculate_price_location(current_price, nearest_support, nearest_resistance):
    logging.debug(f"Calculating price location with current_price: {current_price}, "
                  f"nearest_support: {nearest_support}, nearest_resistance: {nearest_resistance}")
    
    if nearest_support is None or nearest_resistance is None:
        logging.error("Support and resistance levels must not be None.")
        return None
    
    if nearest_resistance == nearest_support:
        logging.warning("Nearest resistance and support are equal, setting price location to 0.")
        return 0
    
    try:
        price_location = (current_price - nearest_support) / (nearest_resistance - nearest_support)
    except ZeroDivisionError:
        logging.error("Division by zero encountered in price location calculation.")
        return None
    
    return price_location 