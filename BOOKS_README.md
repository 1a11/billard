# Books Integration

## Overview
The books feature has been integrated into the project with the following components:

## Routes
- `/books` - Books listing page (grid view of all books)
- `/book/<slug>` - Individual book detail page

## Data Structure

### Books Metadata (`/books/books.json`)
Contains an array of book metadata objects with:
- `id`: Unique identifier
- `title`: Book title
- `author`: Author name
- `slug`: URL-friendly identifier (used in `/book/<slug>` route)
- `imageUrl`: Cover image URL or data URI

### Individual Book Files (`/books/<filename>.json`)
Each book can have a detailed JSON file with:
- `coverUrl`: Book cover image (URL or data URI)
- `author`: Author name
- `title`: Book title
- `subtitle`: Book subtitle/tagline
- `progress`: Object with `currentPage` and `totalPages`
- `status`: Object with `type` ('available', 'checked-out', 'out-of-circulation') and `text`
- `sections`: Array of content sections, each with:
  - `title`: Section title
  - `id`: Section ID
  - `content`: Array of paragraph strings

## Templates
- `templates/books.html` - Books grid listing
- `templates/book.html` - Individual book detail page

Both templates use server-side rendering with Jinja2 (`{{ books|tojson }}` and `{{ book|tojson }}`).

## Navigation
The "books" link has been added to all main navigation menus across templates.

## Notes
- Book uploads and removal are NOT implemented (as requested)
- **Cover image and title always come from `books.json`** - even if a detailed book JSON file exists
- The slug in `books.json` determines which books are accessible
- **Auto-generation of template files**: When you visit a book page for the first time (e.g., `/book/neuromancer`), if the book exists in `books.json` but has no detailed JSON file, the system will:
  1. Display a basic placeholder page
  2. Automatically create a template JSON file named `<slug>.json` in `/books/`
  3. Pre-populate it with metadata from `books.json` and placeholder content
  4. Log the creation with: `Created template book file: <slug>.json`
- **Template content includes**:
  - Cover image from `imageUrl`
  - Title and author from metadata
  - Subtitle: "Not written yet."
  - Progress: 0/0 pages
  - Status: "Status unknown"
  - About section: "Description not written yet."
  - Review section: "Review not written yet."
- **If a specific book JSON file exists**, the system will:
  - Use the cover image and title from `books.json` (overrides the JSON file values)
  - Use author from `books.json` (overrides the JSON file value)
  - Use all other data (subtitle, progress, status, sections) from the JSON file
- You can then manually edit the generated template file to add real content
- Example workflow: Visit `/book/neuromancer` → system creates `/books/neuromancer.json` → edit that file to add details
- Currently only `city-start.json` exists as a manually created demo file (Norwegian Wood)
