# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2009-2014 Alistek ( http://www.alistek.com )
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
import os
import base64
import urllib2

from openerp.osv import orm, fields
from openerp.tools.translate import _

import openerp.tools as tools
from docs_client_lib import DOCSConnection
from openerp.addons.report_aeroo.report_aeroo import aeroo_lock


_url = 'http://www.alistek.com/aeroo_banner/v7_0_report_aeroo.png'


class report_aeroo_installer(orm.TransientModel):
    _name = 'report.aeroo.installer'
    _inherit = 'res.config.installer'
    _rec_name = 'link'
    _logo_image = None

    def _get_image(self):
        if self._logo_image:
            return self._logo_image
        try:
            im = urllib2.urlopen(_url.encode("UTF-8"))
            if im.headers.maintype != 'image':
                raise TypeError(im.headers.maintype)
        except Exception, e:
            path = os.path.join(
                'report_aeroo',
                'config_pixmaps',
                'module_banner.png'
            )
            image_file = file_data = tools.file_open(path, 'rb')
            try:
                file_data = image_file.read()
                self._logo_image = base64.encodestring(file_data)
                return self._logo_image
            finally:
                image_file.close()
        else:
            self._logo_image = base64.encodestring(im.read())
            return self._logo_image

    def _get_image_fn(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        image = self._get_image()
        for rec in self.browse(cr, uid, ids, context=context):
            res[rec.id] = image
        return res

    ### Fields
    _columns = {
        'link': fields.char(
            'Original developer', size=128, readonly=True
        ),
        'config_logo': fields.function(
            _get_image_fn,
            type='binary',
            string='Image',
        ),
    }
    ### ends Fields

    _defaults = {
        'config_logo': _get_image,
        'link':'http://www.alistek.com',
    }

class docs_config_installer(orm.TransientModel):
    _name = 'docs_config.installer'
    _inherit = 'res.config.installer'
    _rec_name = 'host'
    _logo_image = None

    def _get_image(self, cr, uid, context=None):
        if self._logo_image:
            return self._logo_image
        try:
            im = urllib2.urlopen(_url.encode("UTF-8"))
            if im.headers.maintype != 'image':
                raise TypeError(im.headers.maintype)
        except Exception, e:
            path = os.path.join(
                'report_aeroo',
                'config_pixmaps',
                'module_banner.png'
            )
            image_file = file_data = tools.file_open(path, 'rb')
            try:
                file_data = image_file.read()
                self._logo_image = base64.encodestring(file_data)
                return self._logo_image
            finally:
                image_file.close()
        else:
            self._logo_image = base64.encodestring(im.read())
            return self._logo_image

    def _get_image_fn(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        image = self._get_image()
        for rec in self.browse(cr, uid, ids, context=context):
            res[rec.id] = image
        return res

    ### Fields
    _columns = {
        'enabled': fields.boolean('Enabled'),
        'host': fields.char('Host', size=64, required=True),
        'port': fields.integer('Port', required=True),
        'auth_type': fields.selection(
            [('simple', 'Simple Authentication')],
            'Authentication',
        ),
        'username': fields.char('Username', size=32),
        'password': fields.char('Password', size=32),
        'state': fields.selection(
            [('init', 'Init'),
             ('error', 'Error'),
             ('done', 'Done'),
            ],
            'State', select=True, readonly=True
        ),
        'msg': fields.text('Message', readonly=True),
        'error_details': fields.text('Error Details', readonly=True),
        'config_logo': fields.function(
            _get_image_fn,
            type='binary',
            string='Image',
        ),
    }
    ### ends Fields

    def default_get(self, cr, uid, allfields, context=None):
        icp = self.pool['ir.config_parameter']
        defaults = super(docs_config_installer, self).default_get(
            cr, uid, allfields, context=context
        )
        enabled = icp.get_param(cr, uid, 'aeroo.docs_enabled')
        defaults['enabled'] = enabled == 'True' and True or False
        defaults['host'] = icp.get_param(
            cr, uid, 'aeroo.docs_host'
        ) or 'localhost'
        defaults['port'] = int(
            icp.get_param(cr, uid, 'aeroo.docs_port')
        ) or 8989
        defaults['auth_type'] = icp.get_param(
            cr, uid, 'aeroo.docs_auth_type'
        ) or False
        defaults['username'] = icp.get_param(
            cr, uid, 'aeroo.docs_username'
        ) or 'anonymous'
        defaults['password'] = icp.get_param(
            cr, uid, 'aeroo.docs_password'
        ) or 'anonymous'
        return defaults

    def check(self, cr, uid, ids, context=None):
        if not ids:
            return
        icp = self.pool['ir.config_parameter']
        this_obj = self.browse(cr, uid, ids, context=context)[0]
        icp.set_param('aeroo.docs_enabled', str(this_obj.enabled))
        icp.set_param('aeroo.docs_host', this_obj.host)
        icp.set_param('aeroo.docs_port', this_obj.port)
        icp.set_param('aeroo.docs_auth_type', this_obj.auth_type or 'simple')
        icp.set_param('aeroo.docs_username', this_obj.username)
        icp.set_param('aeroo.docs_password', this_obj.password)
        error_details = ''
        state = 'done'
        if this_obj.enabled:
            try:
                fp = tools.file_open('report_aeroo/test_temp.odt', mode='rb')
                file_data = fp.read()
                with aeroo_lock:
                    docs_client = DOCSConnection(
                        this_obj.host, this_obj.port,
                        username=this_obj.username,
                        password=this_obj.password
                    )
                    token = docs_client.upload(file_data)
                    data = docs_client.convert(
                        identifier=token, out_mime='pdf'
                    )
            except Exception as e:
                error_details = str(e)
                state = 'error'
        if state == 'error':
            msg = _(
                'Failure! Connection to DOCS service was not established ' +
                'or convertion to PDF unsuccessful!'
            )
        elif state == 'done' and not this_obj.enabled:
            msg = _('Connection to Aeroo DOCS disabled!')
        else:
            msg = _(
                'Success! Connection to the DOCS service was successfully '+
                'established and PDF convertion is working.'
            )
        this_obj.msg = msg
        this_obj.error_details = error_details
        this_obj.state = state
        mod_obj = this_obj.env['ir.model.data']
        act_obj = this_obj.env['ir.actions.act_window']
        result = mod_obj.get_object_reference(
            'report_aeroo',
            'action_docs_config_wizard'
        )
        act_id = result and result[1] or False
        result = act_obj.search([('id','=',act_id)]).read()[0]
        result['res_id'] = this_obj.id
        return result

    _defaults = {
        'config_logo': _get_image,
        'host': 'localhost',
        'port': 8989,
        'auth_type': False,
        'username': 'anonymous',
        'password': 'anonymous',
        'state': 'init',
        'enabled': False,
    }
