# Billard - Minimal Blog System
[<img src="https://raw.githubusercontent.com/1a11/billard/refs/heads/main/.github/workflows/aidr.svg" height="20">](https://github.com/1a11/billard)

A minimal, procedurally-styled blog system with dynamic article loading, field notes (bracket comments), and HAWK-authenticated admin API.

## Docker Hub

```
docker pull commanderfish/billard-blog
```

## Structure

```
billard/
├── articles/           # Article JSON files (name_month-day.json)
├── templates/          # HTML templates
│   ├── home.html      # Homepage showing latest article
│   ├── article.html   # Article display with line numbers & field notes
│   ├── work.html      # Work/archive page grouped by year
│   └── contact.html   # Contact page
├── server.py          # Flask server with admin API
├── pyproject.toml     # Python dependencies
└── README.md          # This file
```

## Features

- **Dynamic article loading** from JSON files with automatic date parsing
- **Year-grouped archive** on work page with dot-filled formatting
- **Line numbering** for paragraphs (toggleable per article)
- **Block IDs** for easy reference (toggleable per article)
- **Field notes** (bracket comments) positioned per-text-block with SVG braces
- **LaTeX/KaTeX** support for mathematical formulas
- **Responsive design** with mobile breakpoints (768px, 480px)
- **Procedural sticker** generation with triadic color schemes
- **HAWK authentication** for admin API endpoints
- **Environment-based credentials** for production security

## Article Format

Articles are stored as JSON files in the `articles/` directory with the naming format:
```
name_month-day.json
```

Example: `digital_monolith_10-3.json` (October 3rd)

### Article JSON Structure

```json
{
  "header": {
    "name": "article_slug",
    "mainHeader": "Article Title",
    "date": "October 03, 2025",
    "showLineNumbers": true,
    "showBlockIds": false
  },
  "body": [
    {
      "type": "h2",
      "text": "Main Heading"
    },
    {
      "type": "h3",
      "text": "Subheading"
    },
    {
      "type": "p",
      "id": "p-intro",
      "text": "Paragraph text with $LaTeX$ support..."
    },
    {
      "type": "figure",
      "figureType": "image",
      "content": "https://example.com/image.png",
      "caption": "Figure caption",
      "id": "fig-1"
    },
    {
      "type": "figure",
      "figureType": "formula",
      "content": "$$E = mc^2$$",
      "caption": "Formula caption",
      "id": "formula-1"
    }
  ],
  "fieldNotes": [
    {
      "targetId": "p-intro",
      "startLine": 1,
      "endLine": 3,
      "position": "right",
      "text": "Side note text..."
    }
  ]
}
```

### Header Fields

- `name` - Article slug (used in URL, automatically becomes filename prefix)
- `mainHeader` - Display title of the article
- `date` - Full date string (format: "Month DD, YYYY")
- `showLineNumbers` - Boolean to show/hide line numbers
- `showBlockIds` - Boolean to show/hide block ID labels

### Supported Elements

- `h2` - Main title (article header)
- `h3` - Subheadings (section headers)
- `p` - Paragraphs with optional `id` for field note targeting
- `figure` - Images or formulas
  - `figureType`: `"image"` or `"formula"`
  - `content`: URL for images, LaTeX for formulas (wrapped in `$$`)
  - `caption`: Optional caption text
  - `id`: Optional identifier for referencing

**Spacing:** Images and headings have optimized spacing (50px for images, 40px for h3, reduced on mobile).

### Field Notes (Bracket Comments)

Field notes are side annotations with SVG curly braces that attach to specific lines of paragraphs. They are positioned per-text-block for accurate alignment:

- `targetId` - ID of the target paragraph element
- `startLine` - Starting line number (1-indexed, relative to the paragraph)
- `endLine` - Ending line number (inclusive)
- `position` - "left" or "right" of the text column
- `text` - The note content (supports sans-serif styling)

**Note:** Field notes are automatically hidden on mobile devices (768px and below).

## Technical Details

### Article Filename Convention
Articles are automatically saved as: `{name}_{month}-{day}.json`
- Example: `digital_monolith_10-3.json` for October 3rd

### Date Formatting
- Filenames use: `month-day` (e.g., `10-3`)
- Archive displays: `MMM, DD` (e.g., "Oct, 03")
- Full dates use: `Month DD, YYYY` (e.g., "October 03, 2025")
- Upload timestamps are appended automatically

### Authentication
- Uses **HAWK** (HTTP Holder-Of-Key Authentication) for admin routes
- Credentials stored in `CREDENTIALS` dict with environment variable support
- Decorator `@require_hawk_auth` protects admin endpoints
- Default key: `SUPER_LONG_RANDOM_SECRET` (change via `HAWK_KEY` env var)

### Responsive Breakpoints
- **Desktop**: Default (600px content width)
- **Tablet**: 768px and below
- **Mobile**: 480px and below
- Line numbers, field notes, and block IDs hidden on mobile

## Development

### Dependencies
See `pyproject.toml` for full list:
- `flask` - Web framework
- `mohawk` - HAWK authentication
- `mysql-connector-python` - Database support (future)
- `cryptography` - Security utilities
- `requests` - HTTP client

### Styling
- Serif font for body text with `scaleY(1.2)` transform
- Sans-serif for navigation and UI elements
- Triadic color scheme generated procedurally
- Dot-filled spacing between article titles and dates
- Per-block positioning for line numbers and field notes

1. Install dependencies:
```bash
pip install flask mohawk mysql-connector-python cryptography requests
# or use pyproject.toml
pip install -e .
```

2. Set environment variables (optional, for production):
```bash
# Windows PowerShell
$env:HAWK_KEY="your-super-secret-key-here"

# Linux/Mac
export HAWK_KEY="your-super-secret-key-here"
```

3. Run the server:
```bash
python server.py
```

4. Open browser to: `http://localhost:5000`

## Routes

### Public Routes
- `/` - Homepage showing the latest article only
- `/article/<slug>` - Individual article (e.g., `/article/digital_monolith`)
- `/work` - Work/archive page with articles grouped by year
- `/contact` - Contact page

### Admin Routes (HAWK Auth Required)
- `POST /admin/upload` - Upload a new article (JSON body)
- `POST /admin/remove` - Remove an article (requires `filename` in JSON body)

## Admin API Usage

### Upload Article
```bash
# Requires HAWK authentication headers
POST /admin/upload
Content-Type: application/json

{
  "header": {
    "name": "article_name",
    "mainHeader": "Article Title",
    "date": "October 03, 2025",
    "showLineNumbers": true,
    "showBlockIds": false
  },
  "body": [...],
  "fieldNotes": [...]
}
```

### Remove Article
```bash
POST /admin/remove
Content-Type: application/json

{
  "filename": "article_name_10-3.json"
}
```

**Note:** Upload endpoint automatically adds upload timestamp to the article date.

## Security Considerations

1. **Change the HAWK key** in production via environment variable:
   ```bash
   export HAWK_KEY="use-a-long-random-secure-key"
   ```

2. **Use HTTPS** in production to protect HAWK headers

3. **Rotate credentials** periodically by updating the `CREDENTIALS` dict

4. **Restrict admin routes** at the network level if possible

## Future Enhancements

- MySQL database integration for subscription management
- Nonce tracking to prevent replay attacks
- Multi-user credential support
- Article versioning and drafts
- Search functionality
- RSS feed generation


