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
        time.sleep(1)  # Short pause to ensure page is fully loaded

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
                time.sleep(1)  # Short pause to allow next page to load
            except:
                # If there's no "Next" button or it's disabled, we've reached the last page
                break

        # Return the final page response
        return HtmlResponse(self.driver.current_url, body=body, encoding='utf-8', request=request)