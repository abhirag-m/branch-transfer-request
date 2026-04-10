# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class BranchTransferRequestLine(models.Model):
    _name = 'branch.transfer.request.line'
    _description = 'Branch Transfer Request Line'

    request_id = fields.Many2one(
        'branch.transfer.request',
        string='Transfer Request',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        domain=[('type', 'in', ['product', 'consu'])],
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        required=True,
    )
    qty_requested = fields.Float(
        string='Requested Qty',
        required=True,
        default=1.0,
        digits='Product Unit of Measure',
    )
    qty_approved = fields.Float(
        string='Approved Qty',
        digits='Product Unit of Measure',
    )
    return_qty = fields.Float(
        string='Damaged Qty',
        default=0.0,
        digits='Product Unit of Measure',
    )
    notes = fields.Char(string='Notes')

    # Related fields for display
    state = fields.Selection(related='request_id.state', string='Status', store=True)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id

    @api.constrains('qty_requested')
    def _check_qty_requested(self):
        for line in self:
            if line.qty_requested <= 0:
                raise ValidationError(_('Requested quantity must be greater than zero.'))
