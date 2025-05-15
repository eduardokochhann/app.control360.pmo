from app import create_app
from flask import url_for
import sys

app = create_app()

with app.test_request_context():
    routes = []
    for rule in app.url_map.iter_rules():
        if 'notes' in rule.endpoint:
            routes.append({
                'endpoint': rule.endpoint,
                'methods': rule.methods,
                'url': str(rule)
            })
    
    print("\nRotas relacionadas a 'notes':")
    for route in sorted(routes, key=lambda x: x['url']):
        print(f"Endpoint: {route['endpoint']}, URL: {route['url']}, Methods: {route['methods']}") 