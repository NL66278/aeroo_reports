##############################################################################
#
# Copyright (c) 2008-2013 Alistek Ltd (http://www.alistek.com)
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
import md5
import cups
from tempfile import NamedTemporaryFile

from openerp.osv import orm, fields
from openerp.tools.translate import _
from openerp.report import interface


SUPPORTED_PRINT_FORMAT = ('pdf','raw')
SPECIAL_PRINTERS = ('user-def-gen-purpose-printer','user-def-label-printer')


class report_print_actions(orm.TransientModel):
    _name = 'aeroo.print_actions'
    _inherit = 'aeroo.print_actions'

    def report_to_printer(
            self, cr, uid, ids, report_id, printer, context=None):
        context = context or {}
        context['active_ids'] = ids
        report_xml = self.pool.get('ir.actions.report.xml').browse(
            cr, uid, report_id, context=context
        )
        data = {
            'model': report_xml.model,
            'id': context['active_ids'][0],
            'report_type': 'aeroo',
        }
        report = self.pool['ir.actions.report.xml']._lookup_report(
            cr, report_xml.report_name
        )
        res = report.create(
            cr, uid, context['active_ids'], data, context=context
        )
        if res[1] in SUPPORTED_PRINT_FORMAT:
            with NamedTemporaryFile(
                suffix='', prefix='aeroo-print-', delete=False
            ) as temp_file:
                temp_file.write(res[0])
            conn = cups.Connection()
            return conn.printFile(
                printer,
                temp_file.name,
                'Aeroo Print',
                {'copies': report_xml.copies > 0 and
                 str(report_xml.copies) or '1'}
            )
        else:
            raise osv.except_osv(
                _('Warning!'),
                _('Unsupported report format "%s".'
                  " Is not possible direct print to printer.'
                 ) % res[1]
            )
        return False
    
    def to_print(self, cr, uid, ids, context=None):
        recs = self.browse(cr, uid, ids, context=context)
        rep_mod = self.pool['ir.actions.report.xml']
        report_xml = rep_mod.browse(
            cr, uid, context['report_action_id'], context=context
        )[0]
        obj_print_ids = rep_mod.get_strids(c, uid, ids, context=context)
        if recs.printer:
            data = {
                'model': report_xml.model,
                'id': obj_print_ids[0],
                'report_type': 'aeroo',
            }
            report = rep_mod._lookup_report(report_xml.report_name)
            res = report.create(
                cr, uid, obj_print_ids, data, context=context
            )
            if res[1] in SUPPORTED_PRINT_FORMAT:
                with NamedTemporaryFile(suffix='', 
                    prefix='aeroo-print-', delete=False) as temp_file:
                    temp_file.write(res[0])
                conn = cups.Connection()
                conn.printFile(
                    recs[0].printer,
                    temp_file.name,
                    '%s (Aeroo Reports Print)' % report_xml.name, 
                    {'copies':
                        recs[0].copies > 0 and str(recs[0].copies) or '1'
                    }
                )
                return {
                    'type': 'ir.actions.act_window_close'
                }
        new_recs = recs.with_context(aeroo_dont_print_to_pinter = True)
        res = super(report_print_actions, new_recs).to_print()
        return res
    
    def _get_printers(self, cr, uid, context=None):
        prn_ids = self.pool['aeroo.printers'].search(
            cr, uid, [], context=context
        )
        printers = prn_ids.read(
            cr, uid, ['name', 'code', 'state'], context=context
        )
        return [
            (p['code'], p['name']) for p in printers
            if p['code'] not in SPECIAL_PRINTERS
        ]
    
    _columns = {
        'printer': fields.selection(
            selection=_get_printers, 
            string='Print to Printer',
            required=False,
        ),
    }

    def _get_default_printer(self, cr, uid, context):
        report_action_id = context.get('report_action_id', False)
        report_xml = report_action_id and self.pool.get(
            'ir.actions.report.xml'
        ).browse(cr, uid, report_action_id, context=context) or False
        if report_xml and report_xml.printer_id:
            try:
                if report_xml.printer_id.code in SPECIAL_PRINTERS:
                    printer_id = context.get(
                        "def_%s_%s" %
                        tuple(report_xml.printer_id.code.split('-')[-2:]),
                        False
                    )
                    if printer_id:
                        return self.pool.get('aeroo.printers').browse(
                            cr, uid, printer_id, context=context
                        ).code
                else:
                    return report_xml.printer_id.code
            except Exception, e:
                return False
        return False

    _defaults = {
        'printer': _get_default_printer,
    }


class aeroo_printers(orm.Model):
    _name = 'aeroo.printers'
    _description = 'Available printers for Aeroo direct print'
    
    def _get_state(self, cr, uid, ids, field_name, arg, contex=None):
        res = {}
        conn = cups.Connection()
        printers = conn.getPrinters()
        for rec in self.browse(cr, uid, ids, context=context):
            state = printers.get(rec.code, {}).get('printer-state')
            res[id] = state and str(state) or state
        return res
    
    _columns = {
        'name': fields.char(
            string='Description',
            size=256,
            required=True,
        ),
        'code': fields.char(
            string='Name',
            size=64,
            required=True,
        ),
        'note': fields.text(
            string='Details',
        ),
        'group_ids': fields.many2many(
            'res.groups',
            'aeroo_printer_groups_rel',
            'printer_id',
            'group_id',
            'Groups',
        ),
        'state': fields.function(
            _get_state,
            type='selection',
            selection=[
                ('3', _('Idle')),
                ('4', _('Busy')),
                ('5', _('Stopped')),
            ],
            method=True,
            store=False,
            string='State',
        ),
        'active': fields.boolean('Active')
    }

    def search(
            self, cr, user, args, offset=0, limit=None, order=None,
            context=None, count=False):
        if context and not context.get('view_all'):
            args.append(('code','not in',SPECIAL_PRINTERS))
        res = super(aeroo_printers, self).search(
            cr, user, args, offset=offset, limit=limit, order=order,
            context=context, count=count
        )
        return res

    def refresh(self, cr, uid, ids, context={}):
        conn = cups.Connection()
        printers = conn.getPrinters()
        for r in self.browse(cr, uid, ids, context=context):
            data = printers.get(r.code)
            if not data:
                raise osv.except_osv(
                    _('Error!'),
                    _('Printer "%s" not found!') % r.code
                )
            note = '\n'.join(map(
                lambda key: "%s: %s" % (key, data[key]), data
            ))
            r.write({'note':note}, context=context)
        return True

    _defaults = {
        'active': True,
        
    }


class res_users(orm.Model):
    _name = 'res.users'
    _inherit = 'res.users'
    
    _columns = {
        'context_def_purpose_printer': fields.many2one(
            'aeroo.printers',
            string='Default General Purpose Printer',
            method=True,
            domain='[("code","not in",%s)]' % str(SPECIAL_PRINTERS),
            required=False,
            company_dependent=True,
            help="",
        ),
        'context_def_label_printer': fields.many2one(
            'aeroo.printers',
            string='Default Label Printer',
            method=True,
            domain='[("code","not in",%s)]' % str(SPECIAL_PRINTERS),
            required=False,
            company_dependent=True,
            help="",
        ),
    }


class report_xml(orm.Model):
    _name = 'ir.actions.report.xml'
    _inherit = 'ir.actions.report.xml'
    
    _columns = {
        'printer_id': fields.many2one(
            'aeroo.printers',
            string='Printer',
            help="Printer for direct print, or printer selected by default,"
                 " if 'Report Wizard' field is checked."
        ),
    }

    def unlink(self, cr, uid, ids, context={}):
        act_srv_obj = self.pool.get('ir.actions.server')
        reports = self.read(cr, uid, ids, ['report_wizard','printer_id'])
        for r in reports:
            if not r['report_wizard'] and r['printer_id']:
                act_srv_id = act_srv_obj.search(
                    cr, uid, [
                        ('code','like','# %s #' %
                         md5.md5(str(r['id'])).hexdigest())], context=context)
                if act_srv_id:
                    act_srv_obj.unlink(cr, uid, act_srv_id, context=context)
        res = super(report_xml, self).unlink(cr, uid, ids, context)
        return res

    def create(self, cr, user, vals, context=None):
        res_id = super(report_xml, self).create(
            cr, user, vals, context=context
        )
        if (vals.get('report_type') == 'aeroo' and
                not vals.get('report_wizard') and
                vals.get('printer_id')):
            self._set_report_server_action(cr, user, res_id, context=context)
        return res_id

    def write(self, cr, ids, vals, context=None):
        recs = self.browse(cr, ids, context=context)
        for this_obj in recs:
            do_set = False
            if vals.get('report_type', recs.report_type) == 'aeroo':
                report_wizard = vals.get(
                    'report_wizard', this_obj.report_wizard
                )
                printer_id = vals.get(
                    'printer_id', this_obj.printer_id
                )
                if not report_wizard and printer_id:
                    do_set = True
                elif (not printer_id) or report_wizard:
                    self._unset_report_server_action(
                    cr, uid, [this_obj.id], context=context
                )
            super(report_xml, self).write(
                cr, [this_obj.id], vals, context=context
            )
            if do_set:
                self._set_report_server_action(
                    cr, uid, [this_obj.id], context=context
                )
        return True

    def _set_report_server_action(self, cr, uid, ids, context=None):
        context = context or {}
        report_id = isinstance(ids, list) and ids[0] or ids
        report_xml = self.browse(cr, uid, report_id, context=context)
        if not report_xml.report_wizard:
            ir_values_obj = self.pool.get('ir.values')
            event_id = ir_values_obj.search(
                cr, uid, [
                    ('value','=',"ir.actions.report.xml,%s" % report_id),
                ]
            )
            if event_id:
                event_id = event_id[0]
                model_id = self.pool.get('ir.model').search(
                    cr, uid, [('model','=',report_xml.model)],
                    context=context
                )[0]
                python_code = """
# %s #
report_action_id = %s
context['report_action_id'] = report_action_id
print_actions_obj = self.pool.get('aeroo.print_actions')
printer = print_actions_obj._get_default_printer(cr, uid, context)
print_actions_obj.report_to_printer(cr, uid, [obj.id], report_action_id, printer, context=context)
""" % (md5.md5(str(report_id)).hexdigest(), report_id)
                action_data = {'name':report_xml.name,
                               'model_id':model_id,
                               'state':'code',
                               'code':python_code,
                               }
                act_id = self.pool.get('ir.actions.server').create(
                    cr, uid, action_data, context
                )
                ir_values_obj.write(
                    cr, uid, event_id,
                    {'value':"ir.actions.server,%s" % act_id},
                    context=context
                )
                return act_id
        return False
    
    def _unset_report_server_action(self, cr, uid, ids, context=None):
        ir_values_obj = self.pool['ir.values']
        act_srv_obj = self.pool['ir.actions.server']
        act_srv_ids = act_srv_obj.search(
            cr, uid, [
                ('code', 'like', '# %s #' %
                 md5.md5(str(ids[0])).hexdigest()),
                ('code', 'not like',
                 '# THIS ACTION IS DEPRECATED AND CAN BE REMOVED! #')
            ],
            context=context
        )
        if act_srv_ids:
            act_srv_id = act_srv_ids[0]
            event_ids = ir_values_obj.search(
                cr, uid,
                [('value','=',"ir.actions.server,%s" % act_srv_id.id)],
                context=context
            )
            if event_ids:
                event_ids[0].value = "ir.actions.report.xml,%s" % ids[0]
            srv_act_code = act_srv_id.code.splitlines()
            ctx = context.copy()
            ctx['report_action_id'] = ids[0]
            printer = self.pool['aeroo.print_actions']._get_default_printer()
            srv_act_code.insert(2, "printer = '%s'" % printer)
            srv_act_code.pop(-2)
            srv_act_code.append(
                "# THIS ACTION IS DEPRECATED AND CAN BE REMOVED! #"
            )
            act_srv_id.code = '\n'.join(srv_act_code)
            return True
        return False
