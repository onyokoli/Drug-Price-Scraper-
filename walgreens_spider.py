import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from urllib.parse import quote
import json
import sys
import re
from walgreens_selenium_middleware import WalgreensSeleniumMiddleware

class WalgreensSpider(scrapy.Spider):
    name = 'walgreens'
    
    def __init__(self, search_query, *args, **kwargs):
        super(WalgreensSpider, self).__init__(*args, **kwargs)
        self.search_query = search_query
        self.results = []
        # Open the output JSON file and write the opening bracket
        self.file = open('walgreens_products.json', 'w')
        self.file.write('[\n')  # Start of JSON array
        self.first_item = True

    def start_requests(self):
        # Encode the search query for URL
        encoded_query = quote(self.search_query)
        # Start URL with the encoded search query
        url = f'https://www.walgreens.com/search/results.jsp?Ntt={encoded_query}'
        yield scrapy.Request(url, self.parse)

    def parse(self, response):
        # This method is now just a placeholder, as the actual parsing is done in parse_page
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
            # Remove any None values
            item = {k: v for k, v in item.items() if v is not None}
            
            # Only write and yield the item if both name and price are present
            if item.get('name') and item.get('price'):
                self.write_json(item)
                yield item

        # Check for next page
        next_page = response.css('a.next::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse_page)

    def extract_name(self, product):
        brand = product.css('div.brand::text').get('')
        description = product.css('strong.description::text').get('')
        amount = product.css('span.amount::text').get('')
        full_name = f"{brand.strip()} {description.strip()}".strip()
        if amount:
            # Replace "ea" with "ct" in the amount
            amount = amount.strip().replace('ea', 'ct')
            full_name += f" {amount}"
        # Remove "(Actual Item May Vary)" from the name
        cleaned_name = re.sub(r'\s*\(Actual Item May Vary\)\s*', '', full_name, flags=re.IGNORECASE)
        # Remove "-" between any whitespace
        cleaned_name = re.sub(r'\s*-\s*', ' ', cleaned_name)
        # Remove any extra whitespace
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
        
        # Extract all promotional text from the product__deal-container
        promo_container = product.css('.product__deal-container')
        
        # Extract blue text promo
        blue_promo = promo_container.css('.color__text-blue::text').get()
        if blue_promo:
            promos.append(blue_promo.strip())
        
        # Extract red text promo (Buy X, Get Y deal)
        red_promo = promo_container.css('.color__text-red::text').get()
        if red_promo:
            promos.append(red_promo.strip())
        
        # Extract coupon savings
        coupon = promo_container.css('.product__deal.text-elipse a::text').get()
        if coupon:
            promos.append(coupon.strip())
        
        return ' | '.join(promos) if promos else None

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
        self.file.write('\n]')
        self.file.close()

def run_spider(search_query):
    """
    Set up and run the spider.
    """
    # Configure custom settings for the spider
    custom_settings = get_project_settings()
    custom_settings.update({
        'DOWNLOADER_MIDDLEWARES': {
            'walgreens_selenium_middleware.WalgreensSeleniumMiddleware': 800,
        },
        'LOG_LEVEL': 'DEBUG',
        'DOWNLOAD_DELAY': 2,  # Add a delay between requests
        'RANDOMIZE_DOWNLOAD_DELAY': True,
    })
    
    # Create and start the crawler process
    process = CrawlerProcess(custom_settings)
    process.crawl(WalgreensSpider, search_query=search_query)
    process.start()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Please provide a search query.")
        print("Usage: python walgreens_spider.py <search query>")
        sys.exit(1)
    
    search_query = ' '.join(sys.argv[1:])
    run_spider(search_query)