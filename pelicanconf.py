AUTHOR = 'Masoko'
SITENAME = 'WinApps.Masoko.net'
SITESUBTITLE = 'Free software for <i class="fa fa-windows"></i> windows!'
SITEURL = ''

PATH = 'content'
TIMEZONE = 'Europe/Sofia'
DEFAULT_LANG = 'en'
DEFAULT_DATE_FORMAT = '%a %d %B %Y'

THEME = 'theme'

# Feeds are disabled for now; the original site did not expose any.
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None

# --- URL structure: mirrors the original freeappsml.github.io layout ---
ARTICLE_URL = '{slug}.html'
ARTICLE_SAVE_AS = '{slug}.html'

CATEGORY_URL = 'category/{slug}.html'
CATEGORY_SAVE_AS = 'category/{slug}.html'

TAG_URL = 'tag/{slug}.html'
TAG_SAVE_AS = 'tag/{slug}.html'

AUTHOR_URL = 'author/{slug}.html'
AUTHOR_SAVE_AS = 'author/{slug}.html'

PAGE_URL = '{slug}.html'
PAGE_SAVE_AS = '{slug}.html'

INDEX_SAVE_AS = 'index.html'
ARCHIVES_SAVE_AS = 'archives.html'
CATEGORIES_SAVE_AS = 'categories.html'
TAGS_SAVE_AS = 'tags.html'

DIRECT_TEMPLATES = ['index', 'categories', 'tags', 'archives']

DEFAULT_PAGINATION = 10

STATIC_PATHS = ['images', 'extra/CNAME']
EXTRA_PATH_METADATA = {
    'extra/CNAME': {'path': 'CNAME'},
}

PLUGIN_PATHS = ['plugins']
PLUGINS = ['tipue_search_json']

DEFAULT_METADATA = {
    'status': 'published',
}

# Article/page content already contains full raw HTML (buttons, images,
# pros/cons, screenshots) verbatim from the original build, so the HTML
# reader is used as-is with no markdown processing needed.

RELATIVE_URLS = False
