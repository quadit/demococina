import logging
import requests
from odoo import models, api, fields

_logger = logging.getLogger(__name__)
products_details = None


class PosOrder(models.Model):
    _inherit = "pos.order"

    def send_to_kitchen(self, order_name):
        order = self.search([('pos_reference','=',order_name)], limit=1)
        url = "https://client.zuse.solutions/odoo"
        payload = self.prepare_webhook_payload(order.id)
        try:
            requests.post(
                url,
                json=payload,
                headers={"content-type": "application/json"}
            )
            _logger.info("Request successfully sent to ZuseKDS")
        except Exception as e:
            _logger.exception("ZuseKDS: %s" % str(e))


    @api.model
    def _process_order(self, order, draft, existing_order):
        res = super(PosOrder, self)._process_order(order, draft, existing_order)
        if not draft:
            url = "https://client.zuse.solutions/odoo"
            payload = self.prepare_webhook_payload(res)
            try:
                requests.post(
                    url,
                    json=payload,
                    headers={"content-type": "application/json"}
                )
                _logger.info("Request successfully sent to ZuseKDS")
            except Exception as e:
                _logger.exception("ZuseKDS: %s" % str(e))

        return res

    def prepare_webhook_payload(self, order_id):
        context = dict(self._context)
        context.update({
            "lang": "en_US",
            "display_default_code": False
        })
        self = self.with_context(context)

        pos_order = self.sudo().browse(order_id)

        global products_details
        if "line_note" in pos_order.lines:
            products_details = pos_order.lines.read([
                "price_unit", "qty", "price_subtotal", "discount",
                "product_uom_id",
                "tax_ids_after_fiscal_position", "price_subtotal_incl",
                "pack_lot_ids", "product_id", "line_note"
            ])
        else:
            products_details = pos_order.lines.read([
                "price_unit", "qty", "price_subtotal", "discount",
                "product_uom_id",
                "tax_ids_after_fiscal_position", "price_subtotal_incl",
                "pack_lot_ids", "product_id"
            ])
            
        for rec in products_details:
            product_details = rec.pop("product_id")
            product_id = self.env["product.product"].browse(product_details[0])

            rec.update({
                "category": product_id.pos_categ_id.name or "",
                "full_product_name": product_details[1],
                "kitchen_notes": rec.pop("line_note") or "" if "line_note" in rec else ""
            })

        payments_details = pos_order.payment_ids.read([
            "payment_date", "payment_method_id", "amount"
        ])
        for rec in payments_details:
            rec["payment_date"] = rec["payment_date"].strftime("%m/%d/%Y, %H:%M:%S")

        type = 2
        try:
            pos_order_type = pos_order.order_type.name
            if pos_order_type == 'delivery':
                type = 3
            elif pos_order_type == 'dine in':
                type = 1
            elif pos_order_type == 'drive thru':
                type = 4
        except:
            _logger.exception("pos_order_type is not installed")

        kitchen_notes = ""
        try:
            kitchen_notes += pos_order.order_note or ""
        except:
            _logger.exception("pos_order.order_note is not installed")

        return {
            "company_name": pos_order.company_id.name,
            "branch_name": pos_order.config_id.name,
            "data": {
                "currency": pos_order.currency_id.name,
                "customer": pos_order.partner_id.name or "",
                "date": (pos_order.date_order or fields.Datetime.now()) .strftime('%Y-%m-%d %H:%M:%S'),
                "fiscal_position": pos_order.fiscal_position_id.name or "",
                "order_ref": pos_order.name,
                "order_type": type,
                "total_paid": pos_order.amount_paid,
                "total_return": pos_order.amount_return,
                "taxes": pos_order.amount_tax,
                "total": pos_order.amount_total,
                "user": pos_order.user_id.name,
                "note": pos_order.note or "",
                "receipt_number": pos_order.pos_reference,
                "margin": pos_order.margin,
                "margin_percent": pos_order.margin_percent,
                "tip_amount": pos_order.tip_amount,
                "products_details": products_details,
                "payments_details": payments_details,
                "kitchen_notes": kitchen_notes
            }
        }
