# Balilihan Waterworks: Frontend Architecture & UI Framework

This document outlines the modern frontend architecture of the Balilihan Waterworks system. As of 2026, the system has been modernized to use a **"HAT" architecture (HTMX + Alpine + Tailwind)**, blended perfectly with standard Django templating.

## Core Technologies

1. **Tailwind CSS (via CDN)**
   - Used for all styling and utility classes.
   - Provides a highly responsive, modern, and uniform design language (Indigo/Blue primary themes).
   - No custom CSS is required for standard layouts.

2. **HTMX (htmx.org)**
   - Used to create a Single-Page Application (SPA) feel without the complexity of React or Vue.
   - Handles instant search, table pagination, and form submissions without full-page browser reloads.
   - Controlled via HTML attributes (`hx-get`, `hx-post`, `hx-target`).

3. **Bootstrap Icons**
   - Used for all iconography across the dashboard and sidebars (`bi bi-speedometer2`).

4. **Django Components Library**
   - We have extracted common UI elements into reusable templates to ensure Design Uniformity.

---

## The Components Architecture

To keep the frontend code DRY (Don't Repeat Yourself) locally and on GitHub, we never duplicate button or card HTML. Instead, we use the `components/` directory.

### Directory Structure
```
consumers/templates/
├── components/                 # 👈 Reusable UI Building Blocks
│   ├── badge.html
│   ├── button.html
│   ├── card.html
│   └── stat_card.html
├── consumers/                  # Main Page Templates
│   ├── base.html               # Master Layout (Navbar, Sidebar, HTMX/Tailwind scripts)
│   ├── consumer_list.html      # Full-page skeleton
│   └── partials/               # 👈 HTMX Fragments
│       └── consumer_table_only.html
```

### How to Use Components
When building a new page, include the component and pass variables to it.

**Example 1: A Standard Primary Button**
```html
{% include 'components/button.html' with text='Save Consumer' variant='primary' icon='save' type='submit' %}
```

**Example 2: A Warning Badge**
```html
{% include 'components/badge.html' with text='Delinquent' variant='warning' icon='exclamation-triangle' %}
```

**Example 3: A Statistics Dashboard Card**
```html
{% include 'components/stat_card.html' with title='Total Consumers' value='1,200' icon='people' variant='primary' %}
```

---

## HTMX: The SPA Experience

The old architecture required reloading the entire `base.html` (including the sidebar and header) every time you clicked "Next Page" on a table. 

### How we fixed it:
We split the page into two templates:
1. `consumer_list.html`: Contains the search bar and the `div id="consumer-results"`.
2. `partials/consumer_table_only.html`: Contains *only* the `<table>` HTML.

### The Code Loop:
In the HTML search bar (`consumer_list.html`), we add HTMX triggers:
```html
<form hx-get="{% url 'consumers:consumer_list' %}" 
      hx-target="#consumer-results" 
      hx-trigger="input from:#search delay:500ms">
```
*Translation:* When the user types in `#search`, wait 500ms, then call the URL, and put the resulting HTML inside `#consumer-results`.

In the Python backend (`consumer_views.py`), we check if the request came from HTMX:
```python
if request.headers.get('HX-Request'):
    # Return ONLY the table HTML
    return render(request, 'consumers/partials/consumer_table_only.html', context)

# Otherwise, return the full standard page load
return render(request, 'consumers/consumer_list.html', context)
```

## Creating New Features

When a developer builds a new feature on this system, they must:
1. Use `base.html` as the extension wrapper.
2. Build layout using Tailwind CSS standard utility classes.
3. Call `components/` for any buttons, forms, or cards.
4. If a page has a list, search bar, or heavy table, utilize HTMX to render a `partials/` view for instant speeds.
