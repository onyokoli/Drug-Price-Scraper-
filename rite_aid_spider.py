import scrapy
from urllib.parse import quote
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from scrapy.http import HtmlResponse
import time

class RiteAidSeleniumMiddleware:
    def __init__(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    def process_request(self, request, spider):
        self.driver.get(request.url)
        
        # Adjust the selector based on Rite Aid's page structure
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "li.ra-item-container"))
        )

        time.sleep(2)
        
        # Scrape all pages by clicking the "Next" button
        while True:
            # Get the current page source
            body = self.driver.page_source
            response = HtmlResponse(self.driver.current_url, body=body, encoding='utf-8', request=request)
            
            # Process the current page
            for item in spider.parse_page(response):
                yield item

            # Try to click the "Next" button
            try:
                next_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".ra_next:not(.disabled)"))
                )
                next_button.click()
                time.sleep(2)  # Short pause to allow next page to load
            except:
                # If there's no "Next" button or it's disabled, we've reached the last page
                break

        return HtmlResponse(self.driver.current_url, body=body, encoding='utf-8', request=request)
    
    def __del__(self):
        if hasattr(self, 'driver'):
            self.driver.quit()

class RiteAidSpider(scrapy.Spider):
    name = 'riteaid'
    
    def __init__(self, search_query, results, *args, **kwargs):
        super(RiteAidSpider, self).__init__(*args, **kwargs)
        self.search_query = search_query
        self.results = results

    def start_requests(self):
        encoded_query = quote(self.search_query)
        url = f'https://www.riteaid.com/shop/catalogsearch/result/?q={encoded_query}'
        yield scrapy.Request(url, self.parse, meta={'playwright': True})

    def parse(self, response):
        yield from self.parse_page(response)

    def parse_page(self, response):
        self.logger.info(f"Parsing page: {response.url}")
        products = response.css('li.ra-item-container')
        self.logger.info(f"Found {len(products)} products")
        
        if not products:
            self.logger.warning("No products found. Dumping page content for debugging.")
            with open('debug_page_content.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
        
        for product in products:
            item = {
                'name': self.extract_name(product),
                'price': self.extract_price(product),
                'image': product.css('.ra_image::attr(src)').get('').strip(),
                'link': product.css('.mob-product-image::attr(href)').get('').strip(),
                'ratings': self.extract_rating(product.css('.stars::attr(aria-label)').get('').strip()),
                'promo': product.css('.promo-item-desc::text').get('').strip()
            }
            item = {k: v for k, v in item.items() if v is not None}
            if item.get('name') and item.get('price'):
                self.results.append(item)
                yield item

    def extract_name(self, product):
        brand = product.css('p.para-text::text').get('').strip()
        description = product.css('div.ra_prod_name::text').get('').strip()
        full_name = f"{brand} {description}".strip()
        # Remove "(Actual Item May Vary)" from the name
        cleaned_name = re.sub(r'\s*\(Actual Item May Vary\)\s*', '', full_name, flags=re.IGNORECASE)
        # Remove "-" between any whitespace
        cleaned_name = re.sub(r'\s*-\s*', ' ', cleaned_name)
        # Remove commas
        cleaned_name = cleaned_name.replace(',', '')
        # Remove any extra whitespace
        cleaned_name = ' '.join(cleaned_name.split())
        return cleaned_name or None

    def extract_price(self, product):
        price = product.css('.ra_final-price::text').get('').strip()
        return price or None

    def extract_rating(self, rating_text):
        """
        Extract the numeric rating from the rating text.
        """
        if rating_text:
            match = re.search(r'Rating of this product is ([\d.]+) out of 5\.', rating_text)
            return match.group(1) if match else None
        return None
    
