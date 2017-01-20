# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2008-2013 Alistek (http://www.alistek.com) All Rights Reserved.
#                    General contacts <info@alistek.com>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# This module is GPLv3 or newer and incompatible
# with OpenERP SA "AGPL + Private Use License"!
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################
import re

from openerp.osv import orm, fields
from openerp.tools.translate import _
from openerp.osv.orm import except_orm
from openerp.report import interface


class report_print_actions(orm.TransientModel):
    _name = 'aeroo.print_actions'
    _description = 'Aeroo reports print wizard'

    def _reopen(self, res_id, name):
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': res_id,
            'res_model': name,
            'target': 'new',
        }

    def simple_print(self, cr, uid, ids, context=None):
        report_xml = self._get_report(cr, uid, context=context)
        recs = self.browse(cr, uid, ids[0], context=context)
        data = {
            'model': report_xml.model,
            'ids': recs.print_ids,
            'id': context['active_id'],
            'report_type': 'aeroo'
        }
        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_xml.report_name,
            'datas': data,
            'context': context
        }

    def get_strids(self, cr, uid, ids, context=None):
        recs = self.browse(cr, uid, ids[0], context=context)
        valid_input = re.match(
            '^\[\s*((\d+)(\s*,\s*\d+)*)\s*\]$',
            recs.print_ids
        )
        if not valid_input:
            raise except_orm(_("Error"), _("Wrong or not ids!"))
        return eval(recs.print_ids, {})

    def to_print(self, cr, uid, ids, context=None):
        report_xml = self._get_report(cr, uid, context=context)
        obj_print_ids = self.get_strids(cr, uid, ids, context=context)
        print_ids = []
        if ids:
            recs = self.browse(cr, uid, ids[0], context=context)
            if recs.copies <= 1:
                print_ids = obj_print_ids
            else:
                copies = recs.copies
                while(copies):
                    print_ids.extend(obj_print_ids)
                    copies -= 1
        ##### Simple print #####
        data = {
            'model': report_xml.model,
            'ids': print_ids,
            'id': print_ids[0],
            'report_type': 'aeroo'
        }
        res = {
            'type': 'ir.actions.report.xml',
            'report_name': report_xml.report_name,
            'datas': data,
            'context': recs.env.context
        }
        return res

    def _out_formats_get(self, cr, uid, context=None):
        report_xml = self._get_report(cr, uid, context=context)
        if report_xml:
            mtyp_obj = self.pool['report.mimetypes']
            mtyp_ids = mtyp_obj.search(
                cr, uid, [
                    ('compatible_types', '=', report_xml.in_format),
                ],
                context=context
            )
            return [(str(r.id), r.name) for r in mtyp_ids]
        else:
            return []

    _columns = {
        'out_format': fields.selection(
            selection=_out_formats_get,
            string='Output format',
            required=True,
        ),
        'out_format_code': fields.char(
            string='Output format code',
            size=16,
            required=False,
            readonly=True,
        ),
        'copies': fields.integer(
            string='Number of copies',
            required=True,
        ),
        'message': fields.text('Message'),
        'state': fields.selection(
            [('draft','Draft'),
             ('confirm','Confirm'),
             ('done','Done'),
            ],
            'State',
            select=True,
            readonly=True,
        ),
        'print_ids': fields.text(),
        'report_id': fields.many2one(
            'ir.actions.report.xml',
            'Report',
        ),
    }

    def onchange_out_format(
            self, cr, uid, ids, out_format_id, context=None):
        if not out_format_id:
            return {}
        out_format = self.pool['report.mimetypes'].read(
            cr, uid, int(out_format_id), ['code'], context=context)
        return { 'value':
            {'out_format_code': out_format['code']}
        }

    def _get_report(self, cr, uid, context=None):
        report_id = context.get('report_action_id')
        return report_id and self.pool['ir.actions.report.xml'].browse(
            cr, uid, report_id, context=context
        ) or False

    def default_get(self, cr, uid, allfields, context=None):
        res = super(report_print_actions, self).default_get(
            cr, uid, allfields, context=None
        )
        report_xml = self._get_report(cr, uid, context=context)
        lcall = self.search(
            cr, uid, [
                ('report_id', '=', report_xml.id),
                ('create_uid', '=', uid),
            ],
            context=context
        )
        lcall = lcall and lcall[-1] or False
        if 'copies' in allfields:
            res['copies'] = (lcall or report_xml).copies
        if 'out_format' in allfields:
            res['out_format'] = (
                lcall and lcall.out_format or
                str(report_xml.out_format.id)
            )
        if 'out_format_code' in allfields:
            res['out_format_code'] = (
                lcall and lcall.out_format_code or
                report_xml.out_format.code
            )
        if 'print_ids' in allfields:
            res['print_ids'] = context.get('active_ids')
        if 'report_id' in allfields:
            res['report_id'] = report_xml.id
        return res

    _defaults = {
        'state': 'draft',
    }
