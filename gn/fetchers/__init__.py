"""Rejestr adapterów: nazwa z sources.yaml -> funkcja fetch(source) -> list[Item]."""
from . import html_links, rss

ADAPTERS = {
    "rss": rss.fetch,
    "html_links": html_links.fetch,
}
