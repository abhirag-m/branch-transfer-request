# -*- coding: utf-8 -*-

# ============================================================
# WHAT THIS FILE DOES:
# This file defines the main Branch Transfer Request model.
# When Branch 1 needs to send products to Branch 2,
# they create a record here. The workflow goes:
#   Draft → Confirmed → Approved → Done
# When the request is Confirmed, this file automatically sends
# a real-time bell notification + activity task to ALL users
# of the destination branch so they know a request is waiting.
# The model stores who requested it, source branch/warehouse/location,
# destination branch/warehouse/location, and the product lines.
# It also logs every state change in the chatter automatically.
# ============================================================

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BranchTransferRequest(models.Model):
    _name = 'branch.transfer.request'
    _description = 'Branch Transfer Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_request desc, id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
        ('return_requested', 'Return Requested'),
        ('return_approved', 'Return Approved'),
        ('return_done', 'Return Done'),
    ], string='Status', default='draft', tracking=True, copy=False)

    date_request = fields.Datetime(
        string='Request Date',
        default=fields.Datetime.now,
        required=True,
        tracking=True,
    )
    date_approved = fields.Datetime(string='Approved Date', readonly=True)
    date_done = fields.Datetime(string='Done Date', readonly=True)

    # Source Branch & Warehouse
    source_branch_id = fields.Many2one(
        'res.company',
        string='Source Branch',
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    source_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Source Warehouse',
        default=lambda self: self.env['stock.warehouse'].sudo().search([
            ('incharge_user_ids', 'in', self.env.user.id)
        ], limit=1),
    )
    source_location_id = fields.Many2one(
        'stock.location',
        string='Source Location',
    )
    dest_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Destination Warehouse',
        tracking=True,
        check_company=False,
    )
    dest_location_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
        check_company=False,
    )

    # Request Details
    requested_by = fields.Many2one(
        'res.users',
        string='Requested By',
        default=lambda self: self.env.user,
        readonly=True,
        tracking=True,
    )
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
        tracking=True,
    )
    notes = fields.Text(string='Notes')

    line_ids = fields.One2many(
        'branch.transfer.request.line',
        'request_id',
        string='Products',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
    )
    qty_requested = fields.Float(
        string='Requested Qty',
        default=1.0,
        digits='Product Unit of Measure',
    )
    qty_approved = fields.Float(
        string='Approved Qty',
        digits='Product Unit of Measure',
    )

    line_count = fields.Integer(compute='_compute_line_count', string='# Products')

    delivery_id = fields.Many2one(
        'stock.picking',
        string='Delivery Order',
        readonly=True,
        copy=False,
    )

    # =====================================
    # return damage products
    # =====================================
    return_state = fields.Selection([
        ('none', 'None'),
        ('requested', 'Return Requested'),
        ('done', 'Return Done'),
    ], default='none', string='Return Status')

    return_reason = fields.Text(string='Return Reason')
    is_source_incharge = fields.Boolean(compute='_compute_is_source_incharge')
    is_dest_incharge = fields.Boolean(compute='_compute_is_dest_incharge')

    @api.depends('source_warehouse_id')
    def _compute_is_source_incharge(self):
        for rec in self:
            rec.is_source_incharge = self.env.user in rec.source_warehouse_id.sudo().incharge_user_ids

    @api.depends('dest_warehouse_id')
    def _compute_is_dest_incharge(self):
        for rec in self:
            rec.is_dest_incharge = self.env.user in rec.dest_warehouse_id.sudo().incharge_user_ids

    # =====================================================================
    # ONCHANGE METHODS - all unique, no duplicates
    # =====================================================================

    @api.onchange('source_branch_id')
    def _onchange_source_branch(self):
        self.source_warehouse_id = False
        self.source_location_id = False
        self.dest_warehouse_id = False
        self.dest_location_id = False
        if self.source_branch_id:
            warehouses = self.env['stock.warehouse'].sudo().search([
                ('company_id', '=', self.source_branch_id.id)
            ])
            return {
                'domain': {
                    'source_warehouse_id': [('id', 'in', warehouses.ids)],
                    'dest_warehouse_id': [('id', 'in', warehouses.ids)],
                }
            }

    @api.onchange('source_warehouse_id')
    def _onchange_source_warehouse(self):
        self.source_location_id = False
        if self.source_warehouse_id:
            return {
                'domain': {
                    'source_location_id': [
                        ('warehouse_id', '=', self.source_warehouse_id.id),
                        ('usage', '=', 'internal'),
                    ]
                }
            }


    @api.onchange('dest_warehouse_id')
    def _onchange_dest_warehouse(self):
        self.dest_location_id = False
        if self.dest_warehouse_id:
            # sudo() to bypass company restriction and fetch dest warehouse locations
            locations = self.env['stock.location'].sudo().search([
                ('warehouse_id', '=', self.dest_warehouse_id.id),
                ('usage', '=', 'internal'),
            ])
            return {
                'domain': {
                    'dest_location_id': [('id', 'in', locations.ids)]
                }
            }

    # =====================================================================
    # COMPUTE METHODS
    # =====================================================================

    @api.depends('line_ids')
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'branch.transfer.request') or _('New')
        return super().create(vals_list)

    # =====================================================================
    # ACTION METHODS
    # =====================================================================

    def action_confirm(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_('Please add at least one product before confirming.'))
            rec.state = 'confirmed'
            rec._notify_destination_branch()

    def action_approve(self):
        for rec in self:
            # Only destination warehouse incharge users can approve
            if self.env.user not in rec.dest_warehouse_id.sudo().incharge_user_ids:
                raise UserError(_('Only the destination warehouse incharge can approve this request.'))
            if rec.state != 'confirmed':
                raise UserError(_('Only confirmed requests can be approved.'))
            rec.state = 'approved'
            rec.approved_by = self.env.user
            rec.date_approved = fields.Datetime.now()
            rec.with_context(
                mail_notify_force_send=False,
                mail_auto_delete=False,
                mail_create_nosubscribe=True,
                notify=False
            ).message_post(
                body=_('Transfer request has been <b>Approved</b> by %s.') % self.env.user.name,
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

    def action_done(self):
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('Only approved requests can be marked as done.'))
            rec.state = 'done'
            rec.date_done = fields.Datetime.now()
            rec.with_context(
                mail_notify_force_send=False,
                notify=False
            ).message_post(
                body=_('Transfer request has been marked as <b>Done</b>.'),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

    def action_cancel(self):
        for rec in self:
            # Only destination warehouse incharge users can cancel
            if self.env.user not in rec.dest_warehouse_id.sudo().incharge_user_ids:
                raise UserError(_('Only the destination warehouse incharge can cancel this request.'))
            if rec.state == 'done':
                raise UserError(_('Done requests cannot be cancelled.'))
            rec.state = 'cancelled'
            rec.with_context(
                mail_notify_force_send=False,
                notify=False
            ).message_post(
                body=_('Transfer request has been <b>Cancelled</b>.'),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

    def action_reset_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_('Only cancelled requests can be reset to draft.'))
            rec.state = 'draft'

    #==================================
    # for create return
    # =================================
    def action_request_return(self):
        self.ensure_one()
        wizard = self.env['branch.transfer.return.wizard'].create({
            'request_id': self.id,
            'line_ids': [(0, 0, {
                'product_id': line.product_id.id,
                'product_uom_id': line.product_uom_id.id,
                'qty_requested': line.qty_requested,
                'return_qty': 0.0,
            }) for line in self.line_ids],
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Report Damaged Products'),
            'res_model': 'branch.transfer.return.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def action_confirm_return(self):
        self.ensure_one()
        if not self.return_reason:
            raise UserError(_('Please enter a return reason.'))

    def action_create_delivery(self):
        """WH2 creates delivery after approving.
        This reduces stock from WH2 and creates a receipt for WH1.
        """
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('Only approved requests can create a delivery.'))

            # Get delivery operation type from DESTINATION warehouse
            picking_type = self.env['stock.picking.type'].sudo().search([
                ('warehouse_id', '=', rec.dest_warehouse_id.id),
                ('code', '=', 'outgoing'),
            ], limit=1)

            if not picking_type:
                raise UserError(_('No delivery operation type found for destination warehouse.'))

            # Create stock picking (delivery order)
            picking_vals = {
                'picking_type_id': picking_type.id,
                'location_id': rec.dest_location_id.id or picking_type.default_location_src_id.id,
                'location_dest_id': rec.source_location_id.id or picking_type.default_location_dest_id.id,
                'origin': rec.name,
                'move_ids': [(0, 0, {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.qty_requested,
                    'product_uom': line.product_uom_id.id,
                    'location_id': rec.dest_location_id.id or picking_type.default_location_src_id.id,
                    'location_dest_id': rec.source_location_id.id or picking_type.default_location_dest_id.id,
                }) for line in rec.line_ids],
            }

            picking = self.env['stock.picking'].sudo().create(picking_vals)

            # Link delivery to transfer request
            rec.delivery_id = picking.id
            rec.state = 'done'
            rec.date_done = fields.Datetime.now()
            rec.with_context(
                mail_notify_force_send=False,
                notify=False
            ).message_post(
                body=_('Delivery <b>%s</b> has been created.'),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

            # Open the delivery order
            return {
                'type': 'ir.actions.act_window',
                'name': _('Delivery Order'),
                'res_model': 'stock.picking',
                'res_id': picking.id,
                'view_mode': 'form',
                'target': 'current',
            }

    def action_create_receipt(self):
        for rec in self:
            if rec.state not in ('done', 'return_requested'):
                raise UserError(_('Only done requests can create a receipt.'))

            picking_type = self.env['stock.picking.type'].sudo().search([
                ('warehouse_id', '=', rec.source_warehouse_id.id),
                ('code', '=', 'incoming'),
            ], limit=1)

            if not picking_type:
                raise UserError(_('No receipt operation type found for source warehouse.'))

            # ✅ FIX: A line is valid if net qty (requested - damaged) > 0
            valid_lines = [
                (line, line.qty_requested - line.return_qty)
                for line in rec.line_ids
                if (line.qty_requested - line.return_qty) > 0
            ]

            # Block only if ALL lines are fully damaged
            if not valid_lines:
                raise UserError(_(
                    'Cannot create a receipt. All products have been reported as damaged.'
                ))

            picking_vals = {
                'picking_type_id': picking_type.id,
                'location_id': rec.dest_location_id.id or picking_type.default_location_src_id.id,
                'location_dest_id': rec.source_location_id.id or picking_type.default_location_dest_id.id,
                'origin': rec.name,
                # ✅ Use net qty (requested - damaged) not full qty
                'move_ids': [(0, 0, {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': net_qty,
                    'product_uom': line.product_uom_id.id,
                    'location_id': rec.dest_location_id.id or picking_type.default_location_src_id.id,
                    'location_dest_id': rec.source_location_id.id or picking_type.default_location_dest_id.id,
                }) for line, net_qty in valid_lines],
            }

            picking = self.env['stock.picking'].sudo().create(picking_vals)
            rec.date_done = fields.Datetime.now()

            return {
                'type': 'ir.actions.act_window',
                'name': _('Receipt'),
                'res_model': 'stock.picking',
                'res_id': picking.id,
                'view_mode': 'form',
                'target': 'current',
            }

    def action_create_return_receipt(self):
        for rec in self:
            if rec.state != 'done':
                raise UserError(_('Only approved requests can create a receipt.'))

            picking_type = self.env['stock.picking.type'].sudo().search([
                ('warehouse_id', '=', rec.dest_warehouse_id.id),
                ('code', '=', 'incoming'),
            ], limit=1)

            if not picking_type:
                raise UserError(_('No receipt operation type found for source warehouse.'))

            picking_vals = {
                'picking_type_id': picking_type.id,
                'location_id': rec.dest_location_id.id or picking_type.default_location_src_id.id,
                'location_dest_id': rec.source_location_id.id or picking_type.default_location_dest_id.id,
                'origin': rec.name,
                'move_ids': [(0, 0, {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.qty_requested,
                    'product_uom': line.product_uom_id.id,
                    'location_id': rec.dest_location_id.id or picking_type.default_location_src_id.id,
                    'location_dest_id': rec.source_location_id.id or picking_type.default_location_dest_id.id,
                }) for line in rec.line_ids],
            }

            picking = self.env['stock.picking'].sudo().create(picking_vals)
            rec.state = 'done'
            rec.date_done = fields.Datetime.now()

            return {
                'type': 'ir.actions.act_window',
                'name': _('Receipt'),
                'res_model': 'stock.picking',
                'res_id': picking.id,
                'view_mode': 'form',
                'target': 'current',
            }


    # =====================================================================
    # NOTIFICATION METHODS
    # =====================================================================

    def _notify_destination_branch(self):
        self.ensure_one()

        dest_incharge_users = self.dest_warehouse_id.sudo().incharge_user_ids
        source_incharge_users = self.source_warehouse_id.sudo().incharge_user_ids

        # Notify DESTINATION warehouse incharge users via activity
        for user in dest_incharge_users:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=user.id,
                note=_(
                    'Transfer Request received from <b>%s</b>. '
                    'Reference: <b>%s</b>. Please review and approve.'
                ) % (self.source_warehouse_id.name, self.name),
                summary=_('Branch Transfer Request: %s') % self.name,
            )

        # Notify SOURCE warehouse incharge users via activity
        for user in source_incharge_users:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=user.id,
                note=_(
                    'Your Transfer Request <b>%s</b> has been sent to <b>%s</b>. '
                    'Waiting for approval.'
                ) % (self.name, self.dest_warehouse_id.name),
                summary=_('Transfer Request Sent: %s') % self.name,
            )

    def _notify_get_recipients(self, message, msg_vals, **kwargs):
        return []
