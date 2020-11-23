# -*- coding: utf-8 -*-
# © 2009-2014 Alistek <http://www.alistek.com>.
# © 2017 Therp BV <http://therp.nl>.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import base64
import binascii
import encodings
import sys
import os
import imp
import zipimport
import logging

from openerp.osv import orm, fields
from openerp import SUPERUSER_ID
from openerp.tools.translate import _
from openerp.osv.orm import except_orm
from openerp.report.report_sxw import rml_parse
from openerp import netsvc
import openerp.tools as tools
from openerp.tools.config import config

from report_aeroo import Aeroo_report


logger = logging.getLogger('report_aeroo')


class report_stylesheets(orm.Model):
    """
    Aeroo Report Stylesheets
    """
    _name = 'report.stylesheets'
    _description = 'Report Stylesheets'

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'report_styles': fields.binary(
            'Template Stylesheet',
            help='OpenOffice.org stylesheet (.odt)'
        ),
    }


class res_company(orm.Model):
    _name = 'res.company'
    _inherit = 'res.company'

    _columns = {
        'stylesheet_id': fields.many2one(
            'report.stylesheets',
            'Aeroo Global Stylesheet',
        ),
    }


class report_mimetypes(orm.Model):
    """
    Aeroo Report Mime-Type
    """
    _name = 'report.mimetypes'
    _description = 'Report Mime-Types'

    _columns = {
        'name': fields.char('Name', size=64, required=True, readonly=True),
        'code': fields.char('Code', size=16, required=True, readonly=True),
        'compatible_types': fields.char(
            'Compatible Mime-Types',
            size=128,
            readonly=True,
        ),
        'filter_name': fields.char('Filter Name', size=128, readonly=True),
    }


class report_xml(orm.Model):
    _name = 'ir.actions.report.xml'
    _inherit = 'ir.actions.report.xml'

    def aeroo_docs_enabled(self, cr, uid, context=None):
        """Check if Aeroo DOCS connection is enabled."""
        icp = self.pool['ir.config_parameter']
        enabled = icp.get_param(
            cr, SUPERUSER_ID, 'aeroo.docs_enabled', context=context
        )
        return enabled == 'True' and True or False

    def load_from_file(self, cr, path, key):
        class_inst = None
        expected_class = 'Parser'
        try:
            ad = os.path.abspath(
                os.path.join(tools.ustr(config['root_path']), u'addons')
            )
            mod_path_list = map(
                lambda m: os.path.abspath(tools.ustr(m.strip())),
                config['addons_path'].split(',')
            )
            mod_path_list.append(ad)
            mod_path_list = list(set(mod_path_list))
            for mod_path in mod_path_list:
                if os.path.lexists(
                        mod_path + os.path.sep+path.split(os.path.sep)[0]):
                    filepath = mod_path + os.path.sep + path
                    filepath = os.path.normpath(filepath)
                    sys.path.append(os.path.dirname(filepath))
                    mod_name, file_ext = os.path.splitext(
                        os.path.split(filepath)[-1]
                    )
                    mod_name = '%s_%s_%s' % (cr.dbname, mod_name, key)
                    if file_ext.lower() == '.py':
                        py_mod = imp.load_source(mod_name, filepath)
                    elif file_ext.lower() == '.pyc':
                        py_mod = imp.load_compiled(mod_name, filepath)
                    if expected_class in dir(py_mod):
                        class_inst = py_mod.Parser
                    return class_inst
                elif (os.path.lexists(
                        mod_path + os.path.sep + path.split(os.path.sep)[0] +
                        '.zip')):
                    zimp = zipimport.zipimporter(
                        mod_path + os.path.sep + path.split(os.path.sep)[0] +
                        '.zip'
                    )
                    return zimp.load_module(
                        path.split(os.path.sep)[0]
                    ).parser.Parser
        except SyntaxError, e:
            raise except_orm(_('Syntax Error !'), e)
        except Exception, e:
            logger.error(
                'Error loading report parser: %s' +
                (filepath and ' "%s"' % filepath or ''), e
            )
            return None

    def load_from_source(self, source):
        # RPO Strange and dubious method:
        source = "from openerp.report import report_sxw\n" + source
        context = {'Parser': None}
        try:
            exec source.replace('\r', '') in context
            return context['Parser']
        except SyntaxError, e:
            raise except_orm(_('Syntax Error !'), e)
        except Exception, e:
            logger.error(
                "Error in 'load_from_source' method %s" % __name__,
                exc_info=True
            )
            return None

    def link_inherit_report(
            self, cr, uid, ids, new_replace_report_id=False, context=None):
        res = {}
        if not ids:
            return res
        recs = self.browse(cr, uid, ids, context=None)[0]
        if new_replace_report_id:
            inherit_report = recs.browse(new_replace_report_id)
        else:
            inherit_report = recs.replace_report_id  # TODO RPO: report ??
        if inherit_report:
            ir_values_obj = self.pool['ir.values']
            if inherit_report.report_wizard:
                src_action_type = 'ir.actions.act_window'
                action_id = recs.wizard_id
            else:
                src_action_type = 'ir.actions.report.xml'
                action_id = inherit_report.id
            events = ir_values_obj.search(
                cr, uid,
                [('value', '=', "%s,%s" % (src_action_type, action_id))],
                context=context
            )
            if events:
                event = events[0]
                if recs.report_wizard:
                    dest_action_type = 'ir.actions.act_window'
                    if recs.wizard_id:
                        action_id = recs.wizard_id
                    else:
                        action_id = inherit_report._set_report_wizard(
                            cr, uid,
                            [recs.id],
                            linked_report_id=recs.id,
                            report_name=recs.name,
                            context=context
                        )[0]
                        res['wizard_id'] = action_id
                else:
                    dest_action_type = 'ir.actions.report.xml'
                    action_id = recs.id
                event.write(
                    cr, uid, {
                        'value': "%s,%s" % (dest_action_type, action_id)
                    },
                    context=context
                )
        return res

    def unlink_inherit_report(self, cr, uid, ids, context=None):
        res = {}
        if not ids:
            return res
        recs = self.browse(cr, uid, ids, context=None)[0]
        keep_wizard = context.get('keep_wizard') or False
        if recs.replace_report_id:
            irval_obj = self.pool['ir.values']
            if recs.report_wizard:
                src_action_type = 'ir.actions.act_window'
                action_id = recs.wizard_id.id
                if not keep_wizard:
                    res['wizard_id'] = False
            else:
                src_action_type = 'ir.actions.report.xml'
                action_id = recs.id
            event_ids = irval_obj.search(
                cr, uid,
                [('value', '=', "%s,%s" % (src_action_type, action_id))],
                context=context
            )
            if event_ids:
                event_id = event_ids[0]
                if recs.replace_report_id.report_wizard:
                    dest_action_type = 'ir.actions.act_window'
                    action_id = recs.wizard_id.id
                else:
                    dest_action_type = 'ir.actions.report.xml'
                    action_id = recs.replace_report_id.id
                event_id.write(
                    cr, uid,
                    {'value': "%s,%s" % (dest_action_type, action_id)},
                    context=context
                )
            if (not keep_wizard and recs.wizard_id and
                    not res.get('wizard_id', True)):
                recs.wizard_id.unlink()
        return res

    def unregister_report(self, name):
        service_name = 'report.%s' % name
        if netsvc.Service.exists(service_name):
            netsvc.Service.remove(service_name)

    def register_report(self, cr, record):
        parser = rml_parse
        if record['parser_state'] == 'loc' and record['parser_loc']:
            parser = self.load_from_file(
                record['parser_loc'], cr, record['id']
            ) or parser
        elif record['parser_state'] == 'def' and record['parser_def']:
            parser = self.load_from_source(
                record['parser_def']
            ) or parser
        service_name = 'report.%s' % record['report_name']
        if netsvc.Service.exists(service_name):
            netsvc.Service.remove(service_name)
        Aeroo_report(
            service_name,
            record['model'], record['report_rml'],
            parser=parser
        )

    def register_all(self, cr):
        """Will be called on server startup to register all reports to be
        called from the report service.
        """
        super(report_xml, self).register_all(cr)
        cr.execute(
            "SELECT * FROM ir_act_report_xml"
            " WHERE report_type = 'aeroo' and active = true"
            " ORDER BY id"
        )
        records = cr.dictfetchall()
        for record in records:
            self.register_report(cr, record)

    def _report_content(self, cr, uid, ids, field_name, arg, context=None):
        """Fill computed field report_sxw_content."""
        res = super(report_xml, self)._report_content(
            cr, uid, ids, field_name, arg, context=context
        )
        if not ids:
            return res
        for this_obj in self.browse(cr, uid, ids, context=None):
            name = 'report_sxw_content'
            data = this_obj[name + '_data']
            if (this_obj.report_type == 'aeroo' and
                    this_obj.tml_source == 'file' or
                    not data and this_obj.report_sxw):
                fp = None
                try:
                    # TODO: Probably there's a need to check if path to the
                    # report template actually present (???)
                    fp = tools.file_open(this_obj[name[:-8]], mode='rb')
                    data = (
                        this_obj.report_type == 'aeroo' and
                        base64.encodestring(fp.read()) or
                        fp.read()
                    )
                except IOError, e:
                    if e.errno == 13:  # Permission denied on template file
                        raise except_orm(_(e.strerror), e.filename)
                    else:
                        logger.error(
                            "Error in '_report_content' method",
                            exc_info=True
                        )
                except Exception, e:
                    logger.error(
                        "Error in '_report_content' method",
                        exc_info=True
                    )
                    fp = False
                    data = False
                finally:
                    if fp:
                        fp.close()
            res[this_obj.id] = data
        return res

    def _get_encodings(self, cursor, user, context={}):
        l = list(set(encodings._aliases.values()))
        l.sort()
        return zip(l, l)

    def _report_content_inv(
            self, cr, uid, ids, name, value, arg, context=None):
        if value:
            self.write(
                cr, uid, ids,
                {'report_sxw_content': value},
                context=context
            )

    def change_input_format(self, cr, uid, ids, in_format):
        out_format = self.pool['report.mimetypes'].search(
            cr, uid, [('code', '=', in_format)]
        )
        return {
            'value': {'out_format': out_format and out_format[0] or False}
        }

    def _get_in_mimetypes(self, cr, uid, context=None):
        context = context or {}
        mime_obj = self.pool['report.mimetypes']
        domain = (
            context.get('allformats') and [] or
            [('filter_name', '=', False)]
        )
        mime_ids = mime_obj.search(cr, uid, domain, context=context)
        res = mime_obj.read(
            cr, uid, mime_ids, ['code', 'name'], context=context
        )
        return [(r['code'], r['name']) for r in res]

    def _get_extras(self, cr, uid, ids, field_name, arg, context=None):
        """Fill computed field extras."""
        result = {}
        if not ids:
            return result
        for this_obj in self.browse(cr, uid, ids, context=None):
            if self.aeroo_docs_enabled(cr, uid, context=context):
                result[this_obj.id] = 'aeroo_ooo'
            else:
                result[this_obj.id] = False
        return result

    def _get_default_outformat(self, cr, uid, context=None):
        res_ids = self.pool['report.mimetypes'].search(
            cr, uid, [('code', '=', 'oo-odt')], context=context
        )
        return res_ids and res_ids[0] or False

    _columns = {
        'charset': fields.selection(
            _get_encodings,
            string='Charset',
            required=True,
        ),
        'content_fname': fields.char(
            'Override Extension',
            size=64,
            help='Here you can override output file extension'
        ),
        'styles_mode': fields.selection(
            [('default', 'Not used'),
             ('global', 'Global'),
             ('specified', 'Specified')],
            string='Stylesheet',
        ),
        'stylesheet_id': fields.many2one(
            'report.stylesheets',
            'Template Stylesheet',
        ),
        'tml_source': fields.selection(
            [('database', 'Database'),
             ('file', 'File'),
             ('parser', 'Parser')],
            string='Template source',
            default='database',
            select=True,
        ),
        'parser_def': fields.text('Parser Definition'),
        'parser_loc': fields.char(
            'Parser location',
            size=128,
            help="Path to the parser location."
                 " Beginning of the path must start with the module name!\n"
                 "Like this: {module name}/{path to the parser.py file}"
        ),
        'parser_state': fields.selection(
            [('default', _('Default')),
             ('def', _('Definition')),
             ('loc', _('Location'))],
            'State of Parser',
            select=True,
        ),
        # RPO: report type in v7 is char not a selection
        # 'report_type': fields.selection(
        #     selection_add=[('aeroo', 'Aeroo Reports')],
        # ),
        'process_sep': fields.boolean(
            'Process Separately',
            help="Generate the report for each object separately,"
                 " then merge reports."
        ),
        'in_format': fields.selection(
            _get_in_mimetypes,
            string='Template Mime-type',
        ),
        'out_format': fields.many2one(
            'report.mimetypes',
            'Output Mime-type',
        ),
        'report_sxw_content': fields.function(
            _report_content,
            fnct_inv=_report_content_inv,
            string='SXW content',
            type='binary',
            method=True,
        ),
        'active': fields.boolean(
            'Active',
            help='Disables the report if unchecked.'
        ),
        'report_wizard': fields.boolean(
            'Report Wizard',
            help='Adds a standard wizard when the report gets invoked.'
        ),
        'copies': fields.integer(string='Number of Copies'),
        'fallback_false': fields.boolean(
            'Disable Format Fallback',
            help="Raises error on format convertion failure."
                 " Prevents returning original report file type"
                 " if no convertion is available."
        ),
        'extras': fields.function(
            _get_extras,
            string='Extra options',
            type='char',
            method=True,
            size=256,
        ),
        'replace_report_id': fields.many2one(
            'ir.actions.report.xml',
            'Replace Report',
            help='Select a report that should be replaced.'
        ),
        'wizard_id': fields.many2one(
            'ir.actions.act_window',
            'Wizard Action',
        ),
    }
    _defaults = {
        'tml_source': 'database',
        'in_format': 'oo-odt',
        'out_format': _get_default_outformat,
        'charset': 'utf_8',
        'styles_mode': 'default',
        'parser_state': 'default',
        'parser_def': """class Parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(Parser, self).__init__(cr, uid, name, context)
        self.context = context
        self.localcontext.update({})""",
        'active': True,
        'copies': 1,
    }

    def search(
            self, cr, uid, args, offset=0, limit=None, order=None,
            context=None, count=False):
        context = context or {}
        orig_res_ids = super(report_xml, self).search(
            cr, uid, args, offset=offset, limit=limit, order=order,
            context=context, count=count
        )
        by_name = len(args) == 1 and [x for x in args if x[0] == 'report_name']
        if by_name and orig_res_ids and 'print_id' not in context:
            replace_rep = super(report_xml, self).search(
                cr, uid, [('replace_report_id', '=', orig_res_ids[0])],
                offset=offset, limit=limit, order=order,
                context=context, count=count
            )
            if len(replace_rep):
                return replace_rep
        return orig_res_ids

    def fields_view_get(
            self, cr, uid, view_id=None, view_type='form', toolbar=False,
            submenu=False, context=None):
        context = context or {}
        if context.get('default_report_type') == 'aeroo':
            mda_mod = self.pool['ir.model.data']
            if view_type == 'form':
                view_id = mda_mod.get_object_reference(
                    'report_aeroo', 'act_report_xml_view1'
                )[1]
            elif view_type == 'tree':
                view_id = mda_mod.get_object_reference(
                    'report_aeroo', 'act_aeroo_report_xml_view_tree'
                )[1]
        res = super(report_xml, self).fields_view_get(
            cr, uid, view_id, view_type,
            toolbar=toolbar, submenu=submenu, context=context
        )
        return res

    def unlink(self, cr, uid, ids, context=None):
        if not ids:
            return True
        report_record = self.browse(cr, uid, ids, context=None)[0]
        trans_obj = self.pool['ir.translation']
        act_win_obj = self.pool['ir.actions.act_window']
        irval_obj = self.pool['ir.values']
        trans_ids = trans_obj.search(
            cr, uid,
            [('type', '=', 'report'),
             ('res_id', 'in', ids)],
            context=context
        )
        trans_obj.unlink(cr, uid, trans_ids, context=context)
        self.unlink_inherit_report(
            cr, uid, [report_record.id], context=context
        )
        reports = self.read(
            cr, uid, [report_record.id],
            ['report_name', 'model', 'report_wizard', 'replace_report_id'],
            context=context
        )
        for r in reports:
            if r['report_wizard']:
                act_win_ids = act_win_obj.search(
                    cr, uid,
                    [('res_model', '=', 'aeroo.print_actions')],
                    context=context
                )
                act_win_records = act_win_obj.browse(
                    cr, uid, act_win_ids, context=context
                )
                for act_win in act_win_records:
                    act_win_context = eval(act_win.context, {})
                    if act_win_context.get('report_action_id') == r['id']:
                        act_win.unlink()
            else:
                ir_value_ids = irval_obj.search(
                    cr, uid,
                    [('value', '=', 'ir.actions.report.xml,%s' % r['id'])],
                    context=context
                )
                if ir_value_ids:
                    if not r['replace_report_id']:
                        irval_obj.unlink(
                            cr, uid, ir_value_ids, context=context
                        )
                    self.unregister_report(r['report_name'])
        res = super(report_xml, self).unlink(
            cr, uid, [report_record.id], context=context
        )
        return res

    def create(self, cr, uid, vals, context=None):
        """Create report and immediately register service."""
        if 'report_type' not in vals or vals['report_type'] != 'aeroo':
            # If not aeroo report, just do standard create:
            return super(report_xml, self).create(
                cr, uid, vals, context=context
            )
        vals['auto'] = False
        res_id = super(report_xml, self).create(
            cr, uid, vals, context=context
        )
        if vals.get('report_wizard'):
            wizard_id = self._set_report_wizard(
                cr, uid, vals['replace_report_id'] or res_id,
                res_id, linked_report_id=res_id,
                report_name=vals['name'],
                context=context
            )
            self.write(
                cr, uid, [res_id], {'wizard_id': wizard_id},
                context=context
            )
        if vals.get('replace_report_id'):
            self.link_inherit_report(
                cr, uid, res_id,
                new_replace_report_id=vals['replace_report_id'],
                context=context
            )
        try:
            if vals.get('active', False):
                self.register_report(cr, vals)
        except Exception:
            logger.error("Error in report registration", exc_info=True)
            raise except_orm(
                _('Report registration error !'),
                _('Report was not registered in system !')
            )
        return res_id

    def write(self, cr, uid, ids, vals, context=None):
        if 'report_sxw_content_data' in vals:
            if vals['report_sxw_content_data']:
                try:
                    base64.decodestring(vals['report_sxw_content_data'])
                except binascii.Error:
                    vals['report_sxw_content_data'] = False
        recs = self.browse(cr, uid, ids, context=None)[0]
        if vals.get('report_type', recs.report_type) != 'aeroo':
            res = super(report_xml, self).write(
                cr, uid, ids, vals, context=context
            )
            return res
        # Continues if this is Aeroo report
        if (vals.get('report_wizard') and vals.get('active', recs.active) and
                (recs.replace_report_id and
                 vals.get('replace_report_id', True) or
                 not recs.replace_report_id)):
            vals['wizard_id'] = self._set_report_wizard(
                cr, uid,
                report_action_id=recs.ids,
                linked_report_id=vals.get('replace_report_id'),
                context=context
            )
            vals['wizard_id'] = vals['wizard_id'] and vals['wizard_id'][0]
        elif ('report_wizard' in vals and
                not vals['report_wizard'] and recs.report_wizard):
            self._unset_report_wizard(cr, uid, [recs.id], context=context)
            vals['wizard_id'] = False
        # Link / unlink inherited report
        link_vals = {}
        now_unlinked = False
        if 'replace_report_id' in vals and vals.get('active', recs.active):
            if vals['replace_report_id']:
                if (recs.replace_report_id and
                        vals['replace_report_id'] !=
                        recs.replace_report_id.id):
                    context_update = context.copy()
                    context_update['keep_wizard'] = True
                    link_vals.update(
                        self.unlink_inherit_report(
                            cr, uid, [recs.id], context=context_update
                        )
                    )
                    now_unlinked = True
                link_vals.update(
                    self.link_inherit_report(
                        cr, uid, [recs.id],
                        new_replace_report_id=vals['replace_report_id'],
                        context=context
                    )[0])
            else:
                link_vals.update(
                    self.unlink_inherit_report(
                        cr, uid, [recs.id], context=context
                    )[0]
                )
                now_unlinked = True
        try:
            if vals.get('active', recs.active):
                report_vals = {
                    'report_name': vals.get('name', recs.name),
                    'model': vals.get('model', recs.model),
                    'report_rml': vals.get('report_rml', recs.report_rml),
                    'parser_state':
                        vals.get('parser_state', recs.parser_state),
                    'parser_loc':
                        vals.get('parser_loc', recs.parser_loc),
                    'parser_def':
                        vals.get('parser_def', recs.parser_def),
                }
                self.register_report(cr, report_vals)
                if (not recs.active and
                        vals.get('replace_report_id', recs.replace_report_id)):
                    link_vals.update(
                        self.link_inherit_report(
                            cr, uid,
                            new_replace_report_id=vals.get(
                                'replace_report_id', False
                            )
                        )
                    )
            elif not vals.get('active', recs.active):
                self.unregister_report(vals.get('name', recs.name))
                if not now_unlinked:
                    link_vals.update(
                        self.unlink_inherit_report(
                            cr, uid, [recs.id], context=context
                        )
                    )
        except Exception:
            logger.error("Error in report registration", exc_info=True)
            raise except_orm(
                _('Report registration error !'),
                _('Report was not registered in system !')
            )
        vals.update(link_vals)
        res = super(report_xml, self).write(
            cr, uid, ids, vals, context=context
        )
        return res

    def copy(self, cr, uid, ids, default=None, context=None):
        # TODO RPO: Should improve multi record handling:
        recs = self.browse(cr, uid, ids, context=context)[0]
        default = default or {}
        default.update({
            'name': recs.name + " (copy)",
            'report_name': recs.report_name + "_copy",
        })
        return super(report_xml, self).copy(
            cr, uid, ids, default=default, context=context
        )

    def _set_report_wizard(
            self, cr, uid, ids, report_action_id, linked_report_id=False,
            report_name=False, context=None):
        if not ids:
            return False
        ir_values_obj = self.pool['ir.values']
        trans_obj = self.pool['ir.translation']
        recs = self.browse(cr, uid, ids, context=context)[0]
        if linked_report_id:
            linked_report = recs.browse(linked_report_id)
        else:
            linked_report = recs.replace_report_id
        event_id = ir_values_obj.search(
            cr, uid, [
                ('value', '=', "ir.actions.report.xml,%s" % recs.id),
            ],
            context=context
        )
        if not event_id:
            event_id = ir_values_obj.search(
                cr, uid, [
                    ('value', '=', "ir.actions.report.xml,%s" %
                     linked_report.id),
                ],
                context=context
            )
        if event_id:
            action_data = {
                'name': report_name or recs.name,
                'view_mode': 'form',
                'view_type': 'form',
                'target': 'new',
                'res_model': 'aeroo.print_actions',
                'context': {'report_action_id': report_action_id}
            }
            act_id = self.pool['ir.actions.act_window'].create(
                cr, uid, action_data, context=context
            )
            ir_values_obj.write(
                cr, uid, event_id, {
                    'value': "ir.actions.act_window,%s" % act_id,
                },
                context=context
            )
            translation_ids = trans_obj.search(
                cr, uid, [
                    ('res_id', '=', recs.id),
                    ('src', '=', recs.name),
                    ('name', '=', 'ir.actions.report.xml,name'),
                ],
                context=context
            )
            trans_obj.copy(
                cr, uid, translation_ids,
                default={
                    'name': 'ir.actions.act_window,name',
                    'res_id': act_id
                },
                context=context
            )
            return act_id
        return False

    def _unset_report_wizard(self, cr, uid, ids, context=None):
        recs = self.browse(cr, uid, ids, context=context)[0]
        ir_values_obj = self.pool['ir.values']
        trans_obj = self.pool['ir.translation']
        act_win_obj = self.pool['ir.actions.act_window']
        act_win_ids = act_win_obj.search(
            cr, uid, [
                ('res_model', '=', 'aeroo.print_actions'),
                ('context', 'like', str(recs.id)),
            ],
            context=context
        )
        act_win_records = act_win_obj.browse(
            cr, uid, act_win_ids, context=context
        )
        for act_win in act_win_records:
            act_win_context = eval(act_win.context, {})
            if recs.id in act_win_context.get('report_action_id'):
                event_id = ir_values_obj.search(
                    cr, uid,
                    [('value', '=', "ir.actions.act_window,%s" % act_win.id)],
                    context=context
                )
                if event_id:
                    ir_values_obj.write(
                        cr, uid, event_id, {
                            'value': "ir.actions.report.xml,%s" % recs.id,
                        },
                        context=context
                    )
                # Copy translation from window action
                report_xml_ids = trans_obj.search(
                    cr, uid, [
                        ('res_id', '=', recs.id),
                        ('src', '=', act_win.name),
                        ('name', '=', 'ir.actions.report.xml,name'),
                    ],
                    context=context
                )
                trans_langs = map(
                    lambda t: t['lang'],
                    trans_obj.read(
                        cr, uid, report_xml_ids, ['lang'], context=context
                    )
                )
                act_window_trans = trans_obj.search(
                    cr, uid, [
                        ('res_id', '=', act_win.id),
                        ('src', '=', act_win.name),
                        ('name', '=', 'ir.actions.act_window,name'),
                        ('lang', 'not in', trans_langs),
                    ],
                    context=context
                )
                trans_obj.copy(
                    cr, uid, act_window_trans,
                    default={
                        'name': 'ir.actions.report.xml,name',
                        'res_id': recs.id,
                    },
                    context=context
                )
                # Delete wizard name translations
                act_window_trans = trans_obj.search(
                    cr, uid, [
                        ('res_id', '=', act_win.id),
                        ('src', '=', act_win.name),
                        ('name', '=', 'ir.actions.act_window,name'),
                    ],
                    context=context
                )
                trans_obj.unlink(cr, uid, act_window_trans, context=context)
                act_win_obj.unlink(
                    cr, uid, [act_win.id], context=context
                )
                return True
        return False

    def _set_auto_false(self, cr, uid, ids=None, context=None):
        if not ids:
            ids = self.search(
                cr, uid, [
                    ('report_type', '=', 'aeroo'),
                    ('auto', '=', 'True'),
                ],
                context=context
            )
        for id in ids:
            self.write(cr, uid, id, {'auto': False}, context=context)
        return True
