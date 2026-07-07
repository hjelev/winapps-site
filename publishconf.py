import sys
import os

sys.path.append(os.path.dirname(__file__))

from pelicanconf import *

SITEURL = 'https://winapps.masoko.net'
RELATIVE_URLS = False

FEED_DOMAIN = SITEURL
FEED_ALL_ATOM = 'all.atom.xml'
CATEGORY_FEED_ATOM = None
