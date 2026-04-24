import csv
import time
import random
import logging
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def extract_product_info(card, debug=False):
    """Extract product info using flexible text-based fallbacks"""
    try:
        # Try to get the main link first (usually wraps the whole card)
        link_elem = card.find_element(By.TAG_NAME, "a")
        link = link_elem.get_attribute("href")
        if not link or "daraz.com.np" not in link:
            return None

        # Extract visible text content from the card
        card_text = card.text.strip()
        lines = [line.strip() for line in card_text.split('\n') if line.strip()]
        
        if debug:
            print(f"\n🔍 DEBUG - Card text lines ({len(lines)}):")
            for i, line in enumerate(lines[:10]):  # Show first 10 lines
                print(f"  [{i}] {repr(line)}")
            print(f"  Link: {link[:80]}...")

        # Pattern: Title is usually the longest line at the top
        # Price starts with "Rs." or "NPR"
        title = None
        price = None
        
        for line in lines:
            # Price detection
            if re.match(r'^(Rs\.?|NPR\s?)\s*[\d,]+', line, re.I):
                price = line.strip()
                continue
            # Skip metadata lines
            if re.match(r'^\d+\s*sold$|^\(\d+\)$|^[A-Z][a-z]+\s+Province$', line, re.I):
                continue
            # Title: longest non-price, non-metadata line
            if len(line) > 20 and not title:
                title = line.strip()
        
        if title and price:
            # Clean title (remove trailing pipe-separated specs if too long)
            if '|' in title and len(title) > 100:
                title = title.split('|')[0].strip()
            return {"title": title, "price": price, "url": link}
        return None
    except Exception as e:
        if debug:
            print(f"  ❌ Error extracting card: {e}")
        return None

def scrape_daraz_smartphones(base_url="https://www.daraz.com.np/catalog/?q=smartphone", max_pages=2, debug=False):
    driver = setup_driver()
    all_products = []

    try:
        for page in range(1, max_pages + 1):
            url = f"{base_url}&page={page}" if page > 1 else base_url
            logging.info(f"🌐 Loading page {page}: {url}")
            driver.get(url)
            time.sleep(3)  # Wait for React to render

            # Handle cookie banner
            try:
                for selector in ["button[class*='cookie']", "button[id*='accept']", "button[data-test*='accept']"]:
                    btn = driver.find_element(By.CSS_SELECTOR, selector)
                    if btn.is_displayed():
                        btn.click()
                        time.sleep(1)
                        break
            except:
                pass

            # Wait for product grid - look for any product-like container
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'product') or contains(@class, 'item') or @data-qa-locator]//a[@href]"))
            )
            
            # Scroll to load lazy content
            driver.execute_script("window.scrollBy(0, 1200);")
            time.sleep(2)

            # Find all cards: flexible selector approach
            # Try multiple possible container patterns
            card_selectors = [
                "//div[contains(@class, 'product') or contains(@class, 'item') or contains(@class, 'c3e8') or @data-qa-locator='product-item']",
                "//div[@id='root']//div[.//a[contains(@href, '/products/')]]",
                "//div[contains(@class, 'grid')]/div[.//span[contains(text(), 'Rs.')]]"
            ]
            
            cards = []
            for selector in card_selectors:
                cards = driver.find_elements(By.XPATH, selector)
                if len(cards) >= 10:  # Found reasonable number
                    logging.info(f"✅ Using selector: {selector[:60]}...")
                    break
            
            if not cards:
                # Fallback: find all divs containing "Rs." and an anchor
                cards = driver.find_elements(By.XPATH, "//div[.//span[contains(text(), 'Rs.') and .//a]]")
                logging.info(f"🔄 Fallback: found {len(cards)} potential cards")

            logging.info(f"📦 Processing {len(cards)} cards on page {page}")
            
            for i, card in enumerate(cards[:40]):  # Limit per page
                product = extract_product_info(card, debug=debug and i < 3)  # Debug first 3
                if product:
                    product["page"] = page
                    all_products.append(product)
                    if debug and i < 3:
                        print(f"  ✅ Extracted: {product['title'][:50]}... | {product['price']}")

            logging.info(f"✅ Page {page} complete. Total: {len(all_products)} products")
            time.sleep(random.uniform(2, 4))

    except Exception as e:
        logging.error(f"❌ Error: {e}")
        if debug:
            import traceback
            traceback.print_exc()
    finally:
        driver.quit()

    return all_products

def save_to_csv(products, filename="daraz_smartphones.csv"):
    if not products:
        logging.warning("⚠️ No products extracted. Try with debug=True to see raw card content.")
        return
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["page", "title", "price", "url"])
        writer.writeheader()
        writer.writerows(products)
    logging.info(f"💾 Saved {len(products)} products to {filename}")

if __name__ == "__main__":
    # 🔧 SET debug=True to see raw card text and diagnose selectors
    products = scrape_daraz_smartphones(max_pages=2, debug=True)
    save_to_csv(products)