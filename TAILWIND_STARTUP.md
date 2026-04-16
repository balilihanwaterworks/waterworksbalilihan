# Tailwind CSS - Quick Start Guide

## 🚀 Development Setup

### First Time Setup

1. **Install Python Dependencies:**
```bash
pip install -r requirements.txt
```

2. **Install Node Dependencies:**
```bash
cd theme
npm install
cd ..
```

3. **Build Tailwind CSS:**
```bash
cd theme
npm run build
cd ..
```

4. **Collect Static Files:**
```bash
python manage.py collectstatic --noinput
```

5. **Run Development Server:**
```bash
python manage.py runserver
```

---

## 🔄 Daily Development Workflow

### Option 1: Auto-Rebuild (Recommended)

Open TWO terminal windows:

**Terminal 1 - Django Server:**
```bash
python manage.py runserver
```

**Terminal 2 - Tailwind Watcher:**
```bash
cd theme
npm run dev
```

The Tailwind watcher will automatically rebuild CSS when you modify templates!

### Option 2: Manual Rebuild

If you only make occasional changes:

```bash
# Make your template changes
# Then rebuild Tailwind:
cd theme
npm run build
cd ..

# Refresh browser (Ctrl+R or Cmd+R)
```

---

## 🏗️ Production Build

Before deploying to Render:

```bash
# 1. Build minified Tailwind CSS
cd theme
npm run build
cd ..

# 2. Collect all static files
python manage.py collectstatic --noinput

# 3. Test production mode locally (optional)
DEBUG=False python manage.py runserver

# 4. Commit and push
git add .
git commit -m "Tailwind CSS production build"
git push origin main
```

---

## 📁 Important Files

| File | Purpose |
|------|---------|
| `theme/tailwind.config.js` | Tailwind configuration & custom colors |
| `theme/static_src/src/styles.css` | Source CSS (edit this) |
| `theme/static/css/styles.css` | Compiled CSS (auto-generated) |
| `theme/package.json` | NPM scripts |
| `TAILWIND_INTEGRATION_GUIDE.md` | Full documentation |

---

## 🎨 Adding Custom Styles

### Method 1: Use Tailwind Utilities (Preferred)
```html
<div class="bg-primary-600 text-white p-4 rounded-lg shadow-md">
    Content
</div>
```

### Method 2: Custom Component Classes
Edit `theme/static_src/src/styles.css`:

```css
@layer components {
    .my-custom-button {
        @apply px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700;
    }
}
```

Then rebuild:
```bash
cd theme && npm run build
```

---

## ⚙️ Available NPM Scripts

```bash
# Development - watch mode with auto-rebuild
npm run dev

# Production - minified build
npm run build
```

---

## 🐛 Troubleshooting

### CSS Not Loading?
```bash
cd theme
npm run build
cd ..
python manage.py collectstatic --noinput
# Clear browser cache: Ctrl+Shift+R
```

### New Classes Not Working?
Check that `tailwind.config.js` content includes your template paths:
```javascript
content: [
    './templates/**/*.html',
    '../consumers/templates/**/*.html',
    '../**/templates/**/*.html',
],
```

### Development Server Not Showing Changes?
- Make sure Tailwind watcher is running (`npm run dev`)
- Hard refresh browser (Ctrl+Shift+R)
- Check terminal for compilation errors

---

## 📦 Render Deployment

Render automatically handles:
1. ✅ Running `npm install` in theme directory
2. ✅ Running `npm run build`
3. ✅ Running `python manage.py collectstatic`
4. ✅ Starting the application

No extra configuration needed!

---

## ✨ Quick Tips

1. **Use the watcher during development** - saves time!
2. **Always build before committing** - ensure production CSS is ready
3. **Check the integration guide** - lots of examples and patterns
4. **Use custom color classes** - maintain brand consistency
5. **Test responsive design** - mobile, tablet, desktop

---

**Happy Coding! 🎉**
