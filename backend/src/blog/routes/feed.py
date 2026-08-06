"""SEO 路由：feed.xml、sitemap.xml、robots.txt。"""

from __future__ import annotations

from flask import Blueprint, Response

from .. import seo


def build_blueprint(store) -> Blueprint:
    bp = Blueprint("feed", __name__)

    def atom_feed():
        body = seo.build_atom_feed(store)
        return Response(body, mimetype="application/atom+xml; charset=utf-8")

    def sitemap_xml():
        body = seo.build_sitemap(store)
        return Response(body, mimetype="application/xml; charset=utf-8")

    def robots_txt():
        body = seo.build_robots_txt()
        return Response(body, mimetype="text/plain; charset=utf-8")

    bp.add_url_rule("/feed.xml", "atom_feed", atom_feed, methods=["GET"])
    bp.add_url_rule("/sitemap.xml", "sitemap_xml", sitemap_xml, methods=["GET"])
    bp.add_url_rule("/robots.txt", "robots_txt", robots_txt, methods=["GET"])
    return bp
