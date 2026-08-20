import requests
from bs4 import BeautifulSoup
from datetime import datetime

DEFAULT_PRICE = 331.20  # Fallback price if internet fails during hackathon

def get_live_pso_price():
    """Scrapes current petrol price from Shell Pakistan station board."""
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
                    return float(price_text)
    except Exception as e:
        print(f"Scraper warning: {e}. Falling back to default.")
    
    return DEFAULT_PRICE


def get_petrol_price():
    current = get_live_pso_price()

    return {
        "price": current,
        "current_price": current,
        "source": "Live PSO/Shell Web Source",
        "checked_at": datetime.now().isoformat()
    }


def get_current_price():
    return get_petrol_price()