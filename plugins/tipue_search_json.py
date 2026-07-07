# -*- coding: utf-8 -*-
"""
Tipue Search JSON generator.

Adapted from the pelican-plugins "tipue_search" plugin (Copyright (c)
Talha Mansoor) to write a plain tipuesearch_content.json file (instead of a
tipuesearch_content.js file wrapping a JS variable), matching the format the
site's search.html already expects via `mode: 'json'`.
"""
import json
import os.path

from bs4 import BeautifulSoup
from pelican import signals


class TipueSearchJSONGenerator(object):

    def __init__(self, context, settings, path, theme, output_path, *null):
        self.context = context
        self.output_path = output_path
        self.json_nodes = []

    def create_json_node(self, page):
        if getattr(page, 'status', 'published') != 'published':
            return

        soup_title = BeautifulSoup(page.title.replace('&nbsp;', ' '), 'html.parser')
        page_title = soup_title.get_text(' ', strip=True)

        soup_text = BeautifulSoup(page.content, 'html.parser')
        page_text = ' '.join(soup_text.get_text(' ', strip=True).split())

        page_category = page.category.name if getattr(page, 'category', None) else ''

        node = {
            'title': page_title,
            'text': page_text,
            'tags': page_category,
            'url': page.url,
        }
        self.json_nodes.append(node)

    def generate_output(self, writer):
        path = os.path.join(self.output_path, 'tipuesearch_content.json')

        articles = list(self.context['articles'])
        for article in self.context['articles']:
            articles += article.translations

        for article in articles:
            self.create_json_node(article)

        root_node = {'pages': self.json_nodes}
        with open(path, 'w', encoding='utf-8') as fd:
            json.dump(root_node, fd, separators=(',', ':'), ensure_ascii=False)


def get_generators(generators):
    return TipueSearchJSONGenerator


def register():
    signals.get_generators.connect(get_generators)
