from django.contrib.sitemaps import Sitemap

from .models import Property
from .utils import get_public_properties


class PropertySitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.8

    def items(self):
        return get_public_properties()

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()


class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = 'weekly'

    def items(self):
        return ['home', 'contact']

    def location(self, item):
        from django.urls import reverse
        return reverse(item)
