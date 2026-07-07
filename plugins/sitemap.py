# -*- coding: utf-8 -*-
"""
Sitemap generator.

Hand-rolled Pelican plugin (matching the style of tipue_search_json.py)
that writes a sitemap.xml at the output root, listing the homepage,
every published article, every page, every category/tag/author archive
page, and the DIRECT_TEMPLATES pages. Paginated index pages
(index2.html, ...) are never referenced by any context object, so they
are naturally never emitted here.
"""
import os.path
from xml.sax.saxutils import escape

from pelican import signals


class SitemapGenerator(object):

    def __init__(self, context, settings, path, theme, output_path, *null):
        self.context = context
        self.settings = settings
        self.output_path = output_path
        self.siteurl = settings.get('SITEURL', '')
        self.urls = []

    def _add(self, relative_url, lastmod=None):
        self.urls.append((relative_url.lstrip('/'), lastmod))

    def _lastmod_for(self, content_obj):
        dt = getattr(content_obj, 'modified', None) or getattr(content_obj, 'date', None)
        return dt.date().isoformat() if dt else None

    def generate_output(self, writer):
        self._add('', None)

        for article in self.context.get('articles', []):
            self._add(article.url, self._lastmod_for(article))

        for page in self.context.get('pages', []):
            self._add(page.url, self._lastmod_for(page))

        for category, _articles in self.context.get('categories', []):
            self._add(category.url, None)
        for tag, _articles in self.context.get('tags', []):
            self._add(tag.url, None)
        for author, _articles in self.context.get('authors', []):
            self._add(author.url, None)

        for template in self.settings.get('DIRECT_TEMPLATES', []):
            if template == 'index':
                continue
            save_as = self.settings.get(
                '%s_SAVE_AS' % template.upper(), '%s.html' % template
            )
            if save_as:
                self._add(save_as, None)

        self._write()

    def _write(self):
        path = os.path.join(self.output_path, 'sitemap.xml')
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ]
        seen = set()
        for relative_url, lastmod in self.urls:
            if relative_url in seen:
                continue
            seen.add(relative_url)
            loc = '%s/%s' % (self.siteurl, relative_url) if relative_url else '%s/' % self.siteurl
            lines.append('  <url>')
            lines.append('    <loc>%s</loc>' % escape(loc))
            if lastmod:
                lines.append('    <lastmod>%s</lastmod>' % lastmod)
            lines.append('  </url>')
        lines.append('</urlset>')

        with open(path, 'w', encoding='utf-8') as fd:
            fd.write('\n'.join(lines) + '\n')


def get_generators(generators):
    return SitemapGenerator


def register():
    signals.get_generators.connect(get_generators)
