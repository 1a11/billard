import os
import tempfile
import re
import json
import time
import html as _html
import threading
import logging
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

# --- Logging setup ---
logger = logging.getLogger('billard')
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# --- Nonce store for HAWK replay protection ---
# Simple in-memory nonce store with TTL.
_nonce_store = {}
_nonce_lock = threading.Lock()
NONCE_TTL = int(os.environ.get('HAWK_NONCE_TTL', '60'))  # seconds

def seen_nonce(credentials_id, nonce, ts=None):
    """Called by mohawk.Receiver with (credentials_id, nonce, ts).
    Return True if the nonce has already been seen (indicates a replay). Return
    False and record the nonce otherwise. Nonces are namespaced by credentials_id.
    """
    now = time.time()
    key = f"{credentials_id}:{nonce}"
    with _nonce_lock:
        # cleanup expired
        expired = [n for n, exp in _nonce_store.items() if exp < now]
        for n in expired:
            del _nonce_store[n]

        if key in _nonce_store:
            # already seen
            return True

        # mark nonce as seen until TTL
        _nonce_store[key] = now + NONCE_TTL
        return False

# --- Simple in-memory rate limiter ---
_rate_store = {}
_rate_lock = threading.Lock()

def rate_limit(max_requests: int = 10, window_seconds: int = 60):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # use remote addr + endpoint as key
            client = request.remote_addr or 'unknown'
            key = f"{client}:{request.endpoint}"
            now = time.time()
            with _rate_lock:
                count, reset = _rate_store.get(key, (0, now + window_seconds))
                if now > reset:
                    # window expired
                    count = 0
                    reset = now + window_seconds

                if count >= max_requests:
                    # too many requests
                    abort(429)

                _rate_store[key] = (count + 1, reset)

            return f(*args, **kwargs)

        return wrapped

    return decorator

# --- Security headers ---
@app.after_request
def set_security_headers(response):
    response.headers['Strict-Transport-Security'] = 'max-age=63072000; includeSubDomains; preload'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer-when-downgrade'
    response.headers['Permissions-Policy'] = 'geolocation=()'
    csp = ""
    response.headers['Content-Security-Policy'] = csp
    return response


# --- Article sanitizer ---
def sanitize_text(s: str) -> tuple[str, bool]:
    """Escape HTML special chars in string s. Returns (sanitized_string, changed_flag)."""
    if not isinstance(s, str):
        return s, False
    if '<' in s or '>' in s or '&' in s:
        return _html.escape(s), True
    return s, False


def sanitize_article_data(obj):
    """Recursively sanitize all string fields inside article JSON-like structure.
    Returns (sanitized_obj, changed_flag)
    """
    changed = False
    if isinstance(obj, dict):
        new = {}
        for k, v in obj.items():
            sv, ch = sanitize_article_data(v)
            new[k] = sv
            changed = changed or ch
        return new, changed
    elif isinstance(obj, list):
        new_list = []
        for item in obj:
            sv, ch = sanitize_article_data(item)
            new_list.append(sv)
            changed = changed or ch
        return new_list, changed
    elif isinstance(obj, str):
        s2, ch = sanitize_text(obj)
        return s2, ch
    else:
        return obj, False

ARTICLES_DIR = 'articles'
BOOKS_DIR = 'books'
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
                seen_nonce=seen_nonce,
            )
        except HawkFail as e:
            logger.warning('HAWK authentication failed: %s %s %s', request.remote_addr, request.method, request.path)
            abort(401)

        logger.info('HAWK auth success: %s %s %s', request.remote_addr, request.method, request.path)
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
        return (name.lower(), int(month), int(day))
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

def get_all_books():
    """
    Load books metadata from books/books.json
    Returns list of book metadata dicts
    """
    books_meta_path = os.path.join(BOOKS_DIR, 'books.json')
    if not os.path.exists(books_meta_path):
        return []
    
    try:
        with open(books_meta_path, 'r', encoding='utf-8') as f:
            books = json.load(f)
        return books if isinstance(books, list) else []
    except:
        logger.warning('Failed to load books.json')
        return []

def get_book_by_slug(slug):
    """
    Load individual book data from books/<slug>.json or generate basic page from books.json metadata
    Always uses cover and title from books.json metadata when available
    Automatically creates a template JSON file if book exists in books.json but has no detail file
    Returns book data dict or None
    """
    # Normalize slug to lowercase
    slug = slug.lower()
    
    # Validate slug to allow only expected characters to prevent path traversal
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', slug):
        return None
    
    # First, try to get metadata from books.json
    all_books = get_all_books()
    book_metadata = None
    for book_meta in all_books:
        if book_meta.get('slug', '').lower() == slug:
            book_metadata = book_meta
            break
    
    # If slug doesn't exist in books.json at all, return None (404)
    if not book_metadata:
        return None
    
    # Try to load detailed book data from JSON file
    book_data = None
    
    # Try direct slug.json first
    book_path = os.path.abspath(os.path.normpath(os.path.join(BOOKS_DIR, f"{slug}.json")))
    allowed_dir = os.path.abspath(os.path.normpath(BOOKS_DIR))
    
    # Ensure path is inside BOOKS_DIR using os.path.commonpath
    if os.path.commonpath([book_path, allowed_dir]) == allowed_dir:
        if os.path.exists(book_path):
            try:
                with open(book_path, 'r', encoding='utf-8') as f:
                    book_data = json.load(f)
            except:
                logger.warning(f'Failed to load book file: {slug}.json')
    
    # If not found, try to find a file that matches the slug pattern
    if not book_data and os.path.exists(BOOKS_DIR):
        for filename in os.listdir(BOOKS_DIR):
            if filename == 'books.json':
                continue
            if filename.endswith('.json'):
                file_slug = filename[:-5].lower()
                if file_slug == slug:
                    filepath = os.path.join(BOOKS_DIR, filename)
                    fullpath = os.path.abspath(os.path.normpath(filepath))
                    # Ensure path is inside BOOKS_DIR using os.path.commonpath
                    if os.path.commonpath([fullpath, allowed_dir]) == allowed_dir:
                        try:
                            with open(fullpath, 'r', encoding='utf-8') as f:
                                book_data = json.load(f)
                                break
                        except:
                            continue
                    try:
                        with open(fullpath, 'r', encoding='utf-8') as f:
                            book_data = json.load(f)
                            break
                    except:
                        continue
    
    # If detailed book data found, merge with metadata (metadata takes precedence for cover and title)
    if book_data:
        book_data['coverUrl'] = book_metadata.get('imageUrl', book_data.get('coverUrl', ''))
        book_data['title'] = book_metadata.get('title', book_data.get('title', 'Unknown Title'))
        book_data['author'] = book_metadata.get('author', book_data.get('author', 'Unknown Author'))
        # Ensure awards field exists for backward compatibility
        if 'awards' not in book_data:
            book_data['awards'] = []
        return book_data
    
    # If no detailed data, generate basic page from books.json metadata and create template file
    template_data = {
        'coverUrl': book_metadata.get('imageUrl', ''),
        'author': book_metadata.get('author', 'Unknown Author'),
        'title': book_metadata.get('title', 'Unknown Title'),
        'subtitle': 'Not written yet.',
        'progress': {
            'currentPage': 0,
            'totalPages': 0
        },
        'status': {
            'type': 'unknown',
            'text': 'Status unknown'
        },
        'awards': [],
        'sections': [
            {
                'title': 'About',
                'id': 'about-section',
                'content': [
                    'Description not written yet.'
                ]
            },
            {
                'title': 'Review',
                'id': 'review-section',
                'content': [
                    'Review not written yet.'
                ]
            }
        ]
    }
    
    # Create the template file
    try:
        os.makedirs(BOOKS_DIR, exist_ok=True)
        template_path = os.path.join(BOOKS_DIR, f"{slug}.json")
        # Path traversal protection: ensure file stays inside BOOKS_DIR
        safe_template_path = os.path.abspath(os.path.normpath(template_path))
        books_dir_abs = os.path.abspath(BOOKS_DIR)
        if os.path.commonpath([safe_template_path, books_dir_abs]) != books_dir_abs:
            logger.warning(f"Path traversal detected in slug: {slug}")
            raise Exception("Invalid book slug")
        with open(safe_template_path, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, ensure_ascii=False, indent=2)
        logger.info(f'Created template book file: {slug}.json')
    except Exception as e:
        logger.warning(f'Failed to create template book file for {slug}: {e}')
    
    return template_data

@app.route('/')
def home():
    """Home page - shows only the latest article"""
    articles = get_all_articles()
    latest_article = articles[0] if articles else None
    return render_template('home.html', latest_article=latest_article)

@app.route('/article/<slug>')
def article(slug):
    """
    Article page - loads article data from JSON and renders article.html template.
    Slugs and filenames are normalized to lowercase.
    """
    # Normalize requested slug to lowercase
    req_slug = slug.lower()

    # Find the article file matching this slug
    articles = get_all_articles()
    article_data = None

    for art in articles:
        if art.get('slug') == req_slug:
            filepath = os.path.join(ARTICLES_DIR, art['filename'])
            # Defensively ensure the filepath resolves inside ARTICLES_DIR
            fullpath = os.path.abspath(filepath)
            allowed_dir = os.path.abspath(ARTICLES_DIR)
            if not fullpath.startswith(allowed_dir + os.sep) and fullpath != allowed_dir:
                # suspicious path, skip
                continue
            with open(fullpath, 'r', encoding='utf-8') as f:
                article_data = json.load(f)
            break

    if not article_data:
        abort(404)

    # Render the article template with the parsed dict; use Jinja's tojson() in template
    return render_template('article.html', article_json=article_data)

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

@app.route('/books')
def books():
    """Books listing page - displays all books from books.json"""
    all_books = get_all_books()
    return render_template('books.html', books=all_books)

@app.route('/book/<slug>')
def book(slug):
    """Individual book page - loads book data from JSON and renders book.html template"""
    book_data = get_book_by_slug(slug)
    
    if not book_data:
        abort(404)
    
    return render_template('book.html', book=book_data)

@app.post("/admin/upload")
@require_hawk_auth
@rate_limit(max_requests=5, window_seconds=60)
def upload():
    article_data = request.get_json()
    if not article_data:
        abort(400)
    
    header = article_data.get('header', {})
    # Use mainHeader as the article title for filename, fallback to name, fallback to 'untitled'
    raw_name = header.get('mainHeader') or header.get('name') or 'untitled'
    # allow only alphanum, underscore and hyphen in filenames
    name = re.sub(r"[^A-Za-z0-9_\-]", "_", raw_name).strip('_') or 'untitled'
    name = name.lower()
    date_str = header.get('date', '')
    try:
        date_obj = datetime.strptime(date_str, '%B %d, %Y')
        month = date_obj.month
        day = date_obj.day
    except:
        month = 1
        day = 1
        date_obj = datetime(datetime.now().year, month, day)
    
    if len(name) > 20:
        name = name[:20]

    filename = f"{name}_{month}-{day}.json".lower()
    os.makedirs(ARTICLES_DIR, exist_ok=True)
    # Change article data upload date, add upload time
    article_data['header']['date'] = article_data['header'].get('date', '') + " " + datetime.now().strftime('%H:%M:%S')

    # Sanitize article content to avoid HTML/script injection in stored articles
    sanitized_article, changed = sanitize_article_data(article_data)
    if changed:
        logger.info('Article upload sanitized for name=%s date=%s client=%s', name, date_str, request.remote_addr)

    # Write atomically: write sanitized content to a temp file in the articles dir then replace
    temp_fd, temp_path = tempfile.mkstemp(dir=ARTICLES_DIR, prefix=".upload-", suffix=".tmp")
    try:
        with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
            json.dump(sanitized_article, f, ensure_ascii=False, indent=2)
        final_path = os.path.join(ARTICLES_DIR, filename.lower())
        final_abs_path = os.path.abspath(final_path)
        allowed_dir = os.path.abspath(ARTICLES_DIR)
        # Ensure the resolved path is inside the articles directory using a robust containment check
        if not final_abs_path.startswith(allowed_dir + os.sep) and final_abs_path != allowed_dir:
            abort(400)
        os.replace(temp_path, final_path)
    finally:
        # cleanup stray temp file if something went wrong
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

    return jsonify({"ok": True, "sanitized": bool(changed)}), 201

@app.post("/admin/remove")
@require_hawk_auth
@rate_limit(max_requests=5, window_seconds=60)
def remove():
    data = request.get_json()
    if not data or 'filename' not in data:
        abort(400)
    filename = data['filename']
    # Disallow path traversal characters and separators
    if '/' in filename or '\\' in filename or '..' in filename:
        abort(400)
    # sanitize further: only allow simple filenames
    filename = re.sub(r"[^A-Za-z0-9_\-\.]+", "", filename)
    if not filename.endswith('.json'):
        abort(400)

    filepath = os.path.abspath(os.path.join(ARTICLES_DIR, filename))
    allowed_dir = os.path.realpath(os.path.abspath(ARTICLES_DIR))
    # Ensure the resolved path is inside the articles directory (resolve symlinks)
    real_filepath = os.path.realpath(filepath)
    # Prevent deletion of the articles directory itself and ensure containment
    if os.path.commonpath([allowed_dir, real_filepath]) != allowed_dir or real_filepath == allowed_dir:
        abort(400)

    if os.path.exists(filepath):
        os.remove(filepath)
    else:
        abort(404)
    return jsonify({"ok": True}), 200

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
