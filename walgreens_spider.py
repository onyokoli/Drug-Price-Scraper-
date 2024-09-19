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

class WalgreensSeleniumMiddleware:
    def __init__(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-notifications")
        
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    def process_request(self, request, spider):
        self.driver.get(request.url)
        
        WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "li.item"))
        )
        time.sleep(1)

        body = self.driver.page_source
        return HtmlResponse(self.driver.current_url, body=body, encoding='utf-8', request=request)
    
    def __del__(self):
        if hasattr(self, 'driver'):
            self.driver.quit()

class WalgreensSpider(scrapy.Spider):
    name = 'walgreens'
    
    def __init__(self, search_query, results, *args, **kwargs):
        super(WalgreensSpider, self).__init__(*args, **kwargs)
        self.search_query = search_query
        self.results = results

    def start_requests(self):
        encoded_query = quote(self.search_query)
        url = f'https://www.walgreens.com/search/results.jsp?Ntt={encoded_query}'
        yield scrapy.Request(url, self.parse)

    def parse(self, response):
        yield from self.parse_page(response)

    def parse_page(self, response):
        self.logger.info(f"Parsing page: {response.url}")
        products = response.css('li.item')
        self.logger.info(f"Found {len(products)} products")
        
        if not products:
            self.logger.warning("No products found. Dumping page content for debugging.")
            with open('debug_page_content.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
        
        for product in products:
            item = {
                'name': self.extract_name(product),
                'price': self.extract_price(product),
                'rating': self.extract_rating(product),
                'image': product.css('figure.product__img img::attr(src)').get(),
                'link': response.urljoin(product.css('a::attr(href)').get()),
                'promo': self.extract_promo(product),
            }
            item = {k: v for k, v in item.items() if v is not None}
            
            if item.get('name') and item.get('price'):
                self.results.append(item)
                yield item

        next_page = response.css('a.next::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse_page)

    def extract_name(self, product):
        brand = product.css('div.brand::text').get('')
        description = product.css('strong.description::text').get('')
        amount = product.css('span.amount::text').get('')
        full_name = f"{brand.strip()} {description.strip()}".strip()
        if amount:
            amount = amount.strip().replace('ea', 'ct')
            full_name += f" {amount}"
        cleaned_name = re.sub(r'\s*\(Actual Item May Vary\)\s*', '', full_name, flags=re.IGNORECASE)
        cleaned_name = re.sub(r'\s*-\s*', ' ', cleaned_name)
        cleaned_name = ' '.join(cleaned_name.split())
        return cleaned_name or None

    def extract_price(self, product):
        price = product.css('span.body-medium.bold::text').get('')
        return price.strip() or None

    def extract_rating(self, product):
        rating = product.css('img[id^="reviewbazar"]::attr(title)').get('')
        return rating.split(' out of ')[0] if rating else None

    def extract_promo(self, product):
        promos = []
        promo_container = product.css('.product__deal-container')
        blue_promo = promo_container.css('.color__text-blue::text').get()
        if blue_promo:
            promos.append(blue_promo.strip())
        red_promo = promo_container.css('.color__text-red::text').get()
        if red_promo:
            promos.append(red_promo.strip())
        coupon = promo_container.css('.product__deal.text-elipse a::text').get()
        if coupon:
            promos.append(coupon.strip())
        return ' | '.join(promos) if promos else None