import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime

logger = logging.getLogger('safar-e-taleem.petrol')
DEFAULT_PRICE = 343.00  # Current Pakistan petrol price (updated Aug 2026)

def get_live_pso_price():
    """Scrapes current petrol price from Shell Pakistan station board.
    Returns (price, source) tuple so callers know if data is live or fallback.
    """
    url = "https://www.shell.com.pk/shell-stations/shell-station-price-board.html"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            # Look for price table containing 'Super'
            for row in soup.find_all("tr"):
                cells = row.find_all(["td", "th"])
                if cells and "Super" in cells[0].text:
                    price_text = cells[1].text.strip().replace("Rs.", "").replace("/Litre", "").strip()
                    price = float(price_text)
                    return price, 'Live PSO/Shell Web Source'
            # Page loaded but price element not found — layout may have changed
            logger.warning(
                'Shell Pakistan page loaded but could not find Super petrol price row. '
                'Page layout may have changed. Falling back to default Rs %s/L.',
                DEFAULT_PRICE,
            )
    except requests.Timeout:
        logger.warning('Shell Pakistan request timed out (>5s). Using fallback Rs %s/L.', DEFAULT_PRICE)
    except requests.ConnectionError:
        logger.warning('No internet connection to Shell Pakistan. Using fallback Rs %s/L.', DEFAULT_PRICE)
    except Exception as e:
        logger.warning('Scraper error: %s. Using fallback Rs %s/L.', e, DEFAULT_PRICE)
    
    return DEFAULT_PRICE, 'fallback'


def get_petrol_price():
    current, source = get_live_pso_price()

    return {
        "price": current,
        "current_price": current,
        "source": source,
        "checked_at": datetime.now().isoformat()
    }


def get_current_price():
    return get_petrol_price()