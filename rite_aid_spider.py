import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from scrapy import signals
import json
import time
from urllib.parse import quote
import sys
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

class SeleniumMiddleware:
    """
    Middleware to handle JavaScript rendering using Selenium.
    This allows us to interact with dynamic content on the page.
    """
    def __init__(self):
        # Set up Chrome options for headless browsing
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run Chrome in headless mode (no GUI)
        chrome_options.add_argument("--no-sandbox")  # Bypass OS security model
        chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
        
        # Initialize the Chrome WebDriver
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    def process_request(self, request, spider):
        # Navigate to the URL
        self.driver.get(request.url)
        
        # Wait for the product containers to be present on the page
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "li.ra-item-container"))
        )
        time.sleep(2)  # Short pause to ensure page is fully loaded

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

        # Return the final page response
        return HtmlResponse(self.driver.current_url, body=body, encoding='utf-8', request=request)

class RiteAidSpider(scrapy.Spider):
    """
    Spider to scrape product information from Rite Aid's website.
    """
    name = 'riteaid'
    
    def __init__(self, search_query, *args, **kwargs):
        super(RiteAidSpider, self).__init__(*args, **kwargs)
        self.search_query = search_query
        self.results = []
        # Open the output JSON file and write the opening bracket
        self.file = open('riteaid_products.json', 'w')
        self.file.write('[\n')  # Start of JSON array
        self.first_item = True

    def start_requests(self):
        # Encode the search query for URL
        encoded_query = quote(self.search_query)
        # Start URL with the encoded search query
        url = f'https://www.riteaid.com/shop/catalogsearch/result/?q={encoded_query}'
        yield scrapy.Request(url, self.parse)

    def parse(self, response):
        # This method is now just a placeholder, as the actual parsing is done in parse_page
        pass

    def parse_page(self, response):
        """
        Parse a single page of product listings.
        """
        self.logger.info(f"Parsing page: {response.url}")
        products = response.css('li.ra-item-container')
        self.logger.info(f"Found {len(products)} products")
        
        if not products:
            # If no products are found, log a warning and save the page content for debugging
            self.logger.warning("No products found. Dumping page content for debugging.")
            with open('debug_page_content.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
        
        for product in products:
            # Extract product information
            item = {
                'name': self.extract_name(product),
                'price': self.extract_price(product),
                'image': product.css('.ra_image::attr(src)').get('').strip(),
                'link': product.css('.mob-product-image::attr(href)').get('').strip(),
                'ratings': self.extract_rating(product.css('.stars::attr(aria-label)').get('').strip()),
                'promo': product.css('.promo-item-desc::text').get('').strip()
            }
            # Remove any empty string values
            item = {k: v for k, v in item.items() if v}
            
            # Only write and yield the item if both name and price are present
            if item.get('name') and item.get('price'):
                self.write_json(item)
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

    def write_json(self, item):
        """
        Write a single item to the JSON file.
        """
        if not self.first_item:
            self.file.write(',\n')
        else:
            self.first_item = False
        json.dump(item, self.file, ensure_ascii=False, indent=2)
        self.file.flush()  # Ensure the data is written immediately

    def closed(self, reason):
        """
        Called when the spider is closed. Finalize the JSON file.
        """
        self.file.write('\n]')  # End of JSON array
        self.file.close()

def run_spider(search_query):
    """
    Set up and run the spider.
    """
    # Configure custom settings for the spider
    custom_settings = get_project_settings()
    custom_settings.update({
        'DOWNLOADER_MIDDLEWARES': {
            'rite_aid_spider.SeleniumMiddleware': 800,
        },
        'LOG_LEVEL': 'DEBUG',
    })
    
    # Create and start the crawler process
    process = CrawlerProcess(custom_settings)
    process.crawl(RiteAidSpider, search_query=search_query)
    process.start()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Please provide a search query.")
        print("Usage: python rite_aid_spider.py <search query>")
        sys.exit(1)
    
    search_query = ' '.join(sys.argv[1:])
    run_spider(search_query)