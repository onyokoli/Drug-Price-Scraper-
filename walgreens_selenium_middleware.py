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
    """
    Middleware to handle JavaScript rendering for Walgreens using Selenium.
    This allows us to interact with dynamic content on the Walgreens website.
    """
    def __init__(self):
        # Set up Chrome options for headless browsing
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Initialize the Chrome WebDriver
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def process_request(self, request, spider):
        if spider.name != 'walgreens':
            return None

        self.driver.get(request.url)
        
        # Wait for the product list to be present on the page
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "li.item"))
        )
        
        # Short pause to ensure page is fully loaded
        time.sleep(2)

        # Scroll to load all products
        self.scroll_to_bottom()

        # Get the current page source
        body = self.driver.page_source
        return HtmlResponse(self.driver.current_url, body=body, encoding='utf-8', request=request)

    def scroll_to_bottom(self):
        """Scroll to the bottom of the page to load all products."""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    def __del__(self):
        # Close the browser when the middleware is destroyed
        self.driver.quit()