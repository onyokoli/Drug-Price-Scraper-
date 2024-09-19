# import sys
# import json
# from rite_aid_spider import run_spider

# if __name__ == '__main__':
#     if len(sys.argv) < 2:
#         print("Please provide a search query.")
#         print("Usage: python run_riteaid_spider.py <search query>")
#         sys.exit(1)
    
#     search_query = ' '.join(sys.argv[1:])
#     print(f"Running Rite Aid spider for search query: '{search_query}'")
    
#     result_dict = run_spider(search_query)
    
#     print(f"Spider run completed. Found {len(result_dict['products'])} products.")
    
#     # Save the results to a JSON file
#     with open('riteaid_products.json', 'w', encoding='utf-8') as f:
#         json.dump(result_dict, f, ensure_ascii=False, indent=2)
    
#     print("Results saved to 'riteaid_products.json'")

# import sys
# import json
# from walgreens_spider import run_spider

# if __name__ == '__main__':
#     if len(sys.argv) < 2:
#         print("Please provide a search query.")
#         print("Usage: python run_walgreens_spider.py <search query>")
#         sys.exit(1)
    
#     search_query = ' '.join(sys.argv[1:])
#     print(f"Running Walgreens spider for search query: '{search_query}'")
    
#     result_dict = run_spider(search_query)
    
#     print(f"Spider run completed. Found {len(result_dict['products'])} products.")
    
#     # Save the results to a JSON file
#     with open('walgreens_products.json', 'w', encoding='utf-8') as f:
#         json.dump(result_dict, f, ensure_ascii=False, indent=2)
    
#     print("Results saved to 'walgreens_products.json'")

from flask import Flask, jsonify, request
import json
from scrapy.crawler import CrawlerRunner
from scrapy.utils.log import configure_logging
from scrapy.utils.project import get_project_settings
from twisted.internet import reactor
from twisted.web.wsgi import WSGIResource
from twisted.internet import endpoints
from twisted.web.server import Site
from twisted.internet.defer import inlineCallbacks, succeed

# Import your spider classes
from walgreens_spider import WalgreensSpider, WalgreensSeleniumMiddleware
from rite_aid_spider import RiteAidSpider, RiteAidSeleniumMiddleware

app = Flask(__name__)

configure_logging()
settings = get_project_settings()

settings.update({
    'CONCURRENT_REQUESTS': 5000,
    'CONCURRENT_REQUESTS_PER_DOMAIN': 2500,
})

runner = CrawlerRunner(settings)

@inlineCallbacks
def run_spider(spider_class, search_query, results):
    yield runner.crawl(spider_class, search_query=search_query, results=results)

def process_results(walgreens_results, rite_aid_results, search_query):
    # Remove duplicates
    walgreens_results = [dict(t) for t in {tuple(d.items()) for d in walgreens_results}]
    rite_aid_results = [dict(t) for t in {tuple(d.items()) for d in rite_aid_results}]

    # Add source field
    for product in walgreens_results:
        product["source"] = "Walgreens"
    for product in rite_aid_results:
        product["source"] = "Rite Aid"

    # Group results by product name
    grouped_results = {}
    for product in walgreens_results + rite_aid_results:
        name = product["name"]
        if name in grouped_results:
            grouped_results[name].append(product)
        else:
            grouped_results[name] = [product]

    combined_results = {
        "search_query": search_query,
        "products": [{"name": key, "products": value} for key, value in grouped_results.items()]
    }

    return combined_results

@app.route('/crawl', methods=['POST'])
@inlineCallbacks
def crawl_endpoint():
    data = request.get_json()
    if not data or 'search_query' not in data:
        return succeed(jsonify({"error": "Missing search_query parameter"}))

    search_query = data['search_query']
    
    walgreens_results = []
    rite_aid_results = []

    settings.update({
        'DOWNLOADER_MIDDLEWARES': {
            'rite_aid_spider.RiteAidSeleniumMiddleware': 543,
        }
    })
    yield run_spider(RiteAidSpider, search_query, rite_aid_results)

    settings.update({
        'DOWNLOADER_MIDDLEWARES': {
            'walgreens_spider.WalgreensSeleniumMiddleware': 543,
        }
    })
    yield run_spider(WalgreensSpider, search_query, walgreens_results)

    result = process_results(walgreens_results, rite_aid_results, search_query)
    print('\n\n\n\n\n\n')
    print(result)
    print('\n\n\n\n\n\n')
    return succeed(jsonify(result))

if __name__ == '__main__':
    resource = WSGIResource(reactor, reactor.getThreadPool(), app)
    site = Site(resource)
    endpoint = endpoints.TCP4ServerEndpoint(reactor, 5000)
    endpoint.listen(site)
    reactor.run()