# Billard - Minimal Blog System

A minimal, procedurally-styled blog system with dynamic article loading and field notes (bracket comments).

## Structure

```
billard/
├── articles/           # Article JSON files
├── templates/          # HTML templates
│   ├── home.html      # Homepage with article list
│   ├── article.html   # Article display template
│   ├── work.html      # Work/archive page
│   └── contact.html   # Contact page
├── server.py          # Flask server
└── pyproject.toml     # Python dependencies
```

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

### Supported Elements

- `h2` - Main title
- `h3` - Subheadings
- `p` - Paragraphs with optional `id`
- `figure` - Images or formulas
  - `figureType`: "image" or "formula"
  - `content`: URL for images, LaTeX for formulas
  - `caption`: Optional caption text
  - `id`: Optional identifier

### Field Notes (Bracket Comments)

Field notes are side annotations with curly braces that attach to specific lines of paragraphs:

- `targetId`: ID of the target element
- `startLine`: Starting line number (1-indexed)
- `endLine`: Ending line number (inclusive)
- `position`: "left" or "right"
- `text`: The note content

## Running the Server

1. Install dependencies:
```bash
pip install flask
```

2. Run the server:
```bash
python server.py
```

3. Open browser to: `http://localhost:5000`

## Routes

- `/` - Homepage with article list
- `/article/<slug>` - Individual article (e.g., `/article/digital_monolith`)
- `/work` - Work/archive page
- `/contact` - Contact page

## Features

- **Dynamic article loading** from JSON files
- **Line numbering** for paragraphs (toggleable)
- **Block IDs** for easy bracketing reference (toggleable)
- **Field notes** (bracket comments) positioned relative to specific lines
- **LaTeX/KaTeX** support for mathematical formulas
- **Responsive design** with mobile breakpoints
- **Procedural sticker** generation with triadic color schemes
- **Per-block positioning** for accurate line numbers and brackets
