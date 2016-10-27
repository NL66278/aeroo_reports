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
from openerp.osv.orm import orm_exception
from openerp.report import interface


class report_print_actions(models.TransientModel):
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

    def check_if_deferred(self, report_xml, print_ids):
        extras = report_xml.extras.split(',')
        if ('deferred_processing' in extras and
                report_xml.deferred! = 'off' and
                len(print_ids) >= report_xml.deferred_limit):
            return True
        return False

    def start_deferred(self, cr, uid, ids, context=None):
        recs = self.browse(cr, uid, ids[0], context=context)
        report_xml = self.pool.get('ir.actions.report.xml').browse(
            cr, uid, context['report_action_id']
        )
        deferred_proc_obj = self.pool.get('deferred_processing.task')
        process_id = deferred_proc_obj.create(
            cr, uid, {'name':report_xml.name}, context=context
        )
        deferred_proc_obj.new_process(cr, uid, process_id, context=context)
        deferred_proc_obj.start_process_report(
            cr, uid, process_id, recs.print_ids,
            context['report_action_id'], context=context
        )

        mod_obj = self.pool.get('ir.model.data')
        act_obj = self.pool.get('ir.actions.act_window')

        mod_id = mod_obj.search(
            cr, uid, [
                ('name', '=',
                 'action_deferred_processing_task_deferred_processing'),
            ],
            context=context
        )
        res_id = mod_obj.read(cr, uid, mod_id, ['res_id'])['res_id']
        act_win = act_obj.read(
            cr, uid, res_id, [
                'name','type','view_id','res_model','view_type',
                'search_view_id','view_mode','target','context'
            ],
            context=context
        )
        act_win['res_id'] = process_id
        act_win['view_type'] = 'form'
        act_win['view_mode'] = 'form,tree'
        return act_win
    
    def simple_print(self, cr, uid, ids, context=None):
        report_xml = self._get_report(cr, uid, ids, context=context)
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
            raise orm_exception(_("Error"), _("Wrong or not ids!"))
        return eval(recs.print_ids, {})
    
    def to_print(self, cr, uid, ids, context=None):
        report_xml = self._get_report(cr, uid, ids, context=context)
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
            if self.check_if_deferred(report_xml, print_ids):
                self.write(
                        crt, uid, ids, {
                        'state': 'confirm',
                        'message': _(
                            "This process may take too long for interactive \
                            processing. It is advisable to defer the process as a \
                            background process. Do you want to start a deferred \
                            process?"
                        ),
                        'print_ids': str(print_ids)
                    },
                    context=context
                )
                return self._reopen(recs.id, recs._name)
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
        report_xml = self._get_report()
        if report_xml:
            mtyp_obj = self.pool['report.mimetypes']
            mtyp_ids = mtyp_obj.search([('compatible_types','=',report_xml.in_format)])
            return [(str(r.id), r.name) for r in mtyp_ids]
        else:
            return []
    
    ### Fields
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
    ### ends Fields

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
