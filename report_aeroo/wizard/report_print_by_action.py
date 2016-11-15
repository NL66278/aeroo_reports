# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2008-2012 Alistek Ltd (http://www.alistek.com)
#   All Rights Reserved.
#   General contacts <info@alistek.com>
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
from openerp.osv.orm import orm_exception


class report_print_by_action(orm.TransientModel):
    _name = 'aeroo.print_by_action'

    def to_print(self, cr, uid, ids, context=None):
        recs = self.browse(cr, uid, ids, context=context)
        valid_input = re.match(
            '^\s*\[?\s*((\d+)(\s*,\s*\d+)*)\s*\]?\s*$',
            recs[0].object_ids
        )
        valid_input = valid_input and valid_input.group(1) or False
        if not valid_input:
            raise orm_exception(
                _("Error"),
                _("Input single record ID or number of comma separated IDs!")
            )
        print_ids = eval("[%s]" % valid_input, {})
        rep_obj = self.pool['ir.actions.report.xml']
        report = rep_obj.browse(recs.env.context['active_ids'])[0]
        data = {
                'model': report.model,
                'ids': print_ids,
                'id': print_ids[0],
                'report_type': 'aeroo'
                }
        res = {
                'type': 'ir.actions.report.xml',
                'report_name': report.report_name,
                'datas': data,
                'context': recs.env.context
                }
        return res

    # Fields
    _columns = {
        'name': fields.text('Object Model', readonly=True),
        'object_ids': fields.char(
            'Object IDs', size=250, required=True,
            help="Single ID or number of comma separated record IDs"
        ),
    }
    # ends Fields

    def fields_view_get(
            self, cr, uid, view_id=None, view_type='form', toolbar=False,
            submenu=False, context=None):
        context = context or {}
        if context.get('active_ids'):
            report = self.pool['ir.actions.report.xml'].browse(
                cr, uid, context['active_ids'], context=context
            )
            if report.report_name == 'aeroo.printscreen.list':
                raise orm_exception(
                    _("Error"),
                    _("Print Screen report does not support"
                      " this functionality!")
                )
        res = super(report_print_by_action, self).fields_view_get(
            cr, uid, view_id, view_type, toolbar=toolbar, submenu=submenu,
            context=context
        )
        return res

    def _get_model(self, cr, uid, context=None):
        rep_obj = self.pool['ir.actions.report.xml']
        report = rep_obj.browse(
            cr, uid, context['active_ids'], context=context
        )
        return report[0].model

    def _get_last_ids(self, cr, uid, context=None):
        last_call = self.search(
            cr, uid, [
                ('name', '=', self._get_model()),
                ('create_uid', '=', self.env.uid),
            ],
            context=context
        )
        return last_call and last_call[-1].object_ids or False

    _defaults = {
       'name': _get_model,
       'object_ids': _get_last_ids,
    }
