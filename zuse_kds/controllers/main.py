import json

from odoo import http
from odoo.http import request


class OdooKdsIntegration(http.Controller):
    @http.route(route="/pos_category", methods=["GET"], csrf=False,
                type="http", auth="public", cors="*")
    def pos_category(self):
        pos_category = request.env["pos.category"].sudo().search_read(
            [], ["name"]
        )
        for category in pos_category:
            del category["id"]
            
        return json.dumps({
            "data": pos_category
        })