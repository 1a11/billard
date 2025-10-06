import os
import re
import json
import calendar
import secrets
import requests

from datetime import datetime
from collections import defaultdict
from functools import wraps

from flask import Flask, render_template, jsonify, abort, request, redirect, url_for
from mohawk import Receiver
from mohawk.exc import HawkFail

app = Flask(__name__, template_folder='templates')

ARTICLES_DIR = 'articles'
CREDENTIALS = {
    "billard": {
        "id": "billard", 
        "key": os.environ.get("HAWK_KEY", None),
        "algorithm": "sha256"
    }
}

if not CREDENTIALS["billard"]["key"]:
    raise ValueError("HAWK_KEY environment variable not set. Engine will not start.")

def lookup_credentials(creds_id):
    return CREDENTIALS.get(creds_id)

def content_handler(req):
    # return raw body and content type for payload validation
    return request.get_data(), request.headers.get("Content-Type", "")

def require_hawk_auth(f):
    """
    Decorator to require HAWK authentication for a route
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            Receiver(
                credentials_map=lookup_credentials,
                request_header=request.headers.get("Authorization"),
                url=request.url,
                method=request.method,
                content=content_handler(None)[0],
                content_type=content_handler(None)[1],
                seen_nonce=None
            )
        except HawkFail as e:
            abort(401)
        
        return f(*args, **kwargs)
    
    return decorated_function

def parse_article_filename(filename):
    """
    Parse article filename in format: name_month-day.json
    Returns (name, month, day) or None if invalid format
    """
    if not filename.endswith('.json'):
        return None
    
    # Remove .json extension
    name_without_ext = filename[:-5]
    
    if len(name_without_ext) > 20:
        name_without_ext = name_without_ext[:20]

    # Match pattern: name_month-day
    match = re.match(r'^(.+)_(\d{1,2})-(\d{1,2})$', name_without_ext)
    if match:
        name, month, day = match.groups()
        return (name, int(month), int(day))
    return None

def get_all_articles():
    """
    Scan the articles directory and return list of articles with metadata
    Returns list of dicts with: filename, name, month, day, date_str, title, year
    """
    articles = []
    current_year = datetime.now().year
    
    if not os.path.exists(ARTICLES_DIR):
        return articles
    
    for filename in os.listdir(ARTICLES_DIR):
        parsed = parse_article_filename(filename)
        if parsed:
            name, month, day = parsed
            
            # Load the JSON to get the actual title and date
            filepath = os.path.join(ARTICLES_DIR, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    title = data.get('header', {}).get('mainHeader', name.replace('_', ' ').title())
                    
                    # Try to parse year from the full date in the header
                    full_date = data.get('header', {}).get('date', '')
                    year = current_year
                    if full_date:
                        try:
                            parsed_date = datetime.strptime(full_date, '%B %d, %Y')
                            year = parsed_date.year
                        except:
                            pass
                    
                    # Format date as "MMM, DD" (e.g., "Dec, 24")
                    month_name = calendar.month_abbr[month]
                    date_str = f"{month_name}, {day:02d}"
                    
            except:
                title = "Failed to load article title :("
                month_name = calendar.month_abbr[month]
                date_str = f"{month_name}, {day:02d}"
                year = current_year
            
            articles.append({
                'filename': filename,
                'slug': name,
                'month': month,
                'day': day,
                'date_str': date_str,
                'title': title,
                'year': year
            })
    
    # Sort by year (descending), then month (descending), then day (descending)
    articles.sort(key=lambda x: (x['year'], x['month'], x['day']), reverse=True)
    
    return articles

def group_articles_by_year(articles):
    """Group articles by year for the work page"""
    grouped = defaultdict(list)
    for article in articles:
        grouped[article['year']].append(article)
    
    # Sort years in descending order
    return dict(sorted(grouped.items(), reverse=True))

@app.route('/')
def home():
    """Home page - shows only the latest article"""
    articles = get_all_articles()
    latest_article = articles[0] if articles else None
    return render_template('home.html', latest_article=latest_article)

@app.route('/article/<slug>')
def article(slug):
    """
    Article page - loads article data from JSON and renders article.html template
    slug is the article name (without month-day)
    """
    # Find the article file matching this slug
    articles = get_all_articles()
    article_data = None
    
    for art in articles:
        if art['slug'] == slug:
            filepath = os.path.join(ARTICLES_DIR, art['filename'])
            with open(filepath, 'r', encoding='utf-8') as f:
                article_data = json.load(f)
            break
    
    if not article_data:
        abort(404)
    
    # Render the article template with the JSON data embedded
    return render_template('article.html', article_json=json.dumps(article_data))

@app.route('/work')
def work():
    """Work/archive page - lists all articles grouped by year"""
    articles = get_all_articles()
    articles_by_year = group_articles_by_year(articles)
    return render_template('work.html', articles_by_year=articles_by_year)

@app.route('/contact')
def contact():
    """Contact page"""
    return render_template('contact.html')

@app.post("/admin/upload")
@require_hawk_auth
def upload():
    article_data = request.get_json()
    if not article_data:
        abort(400)
    
    header = article_data.get('header', {})
    name = header.get('name', 'untitled').replace(' ', '_')
    date_str = header.get('date', '')
    try:
        date_obj = datetime.strptime(date_str, '%B %d, %Y')
        month = date_obj.month
        day = date_obj.day
    except:
        month = 1
        day = 1
        date_obj = datetime(datetime.now().year, month, day)
    
    name = name.replace('/', '_').replace('\\', '_')
    if len(name) > 20:
        name = name[:20]

    filename = f"{name}_{month}-{day}.json"
    filepath = os.path.join(ARTICLES_DIR, filename)
    os.makedirs(ARTICLES_DIR, exist_ok=True)
    # Change article data upoad date, add upload time
    article_data['header']['date'] = article_data['header']['date'] + " " + datetime.now().strftime('%H:%M:%S')
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(article_data, f, ensure_ascii=False, indent=2)


    return jsonify({"ok": True}), 201

@app.post("/admin/remove")
@require_hawk_auth
def remove():
    data = request.get_json()
    if not data or 'filename' not in data:
        abort(400)
    filename = data['filename']
    filename = filename.replace('/', '_').replace('\\', '_')
    if not filename.endswith('.json'):
        abort(400)
    filepath = os.path.join(ARTICLES_DIR, filename)
     
    if os.path.exists(filepath):
        os.remove(filepath)
    else:
        abort(404)
    return jsonify({"ok": True}), 200

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
