# -*- coding: utf-8 -*-
from werkzeug.wrappers import Response
from odoo import http
import logging
import uuid
import json

_logger = logging.getLogger(__name__)


class Evo(http.Controller):
    @http.route('/evo/connector/<uuid:identifier>', auth='public', csrf=False, methods=['POST'], type="http")
    def index(self, identifier: uuid.UUID, **kw):
        connector = http.request.env['evo_connector'].sudo(flag=True).search(
            [
                ('enabled', '=', True), ('uuid', '=', str(identifier))
            ],
        )
        if not len(connector):
            # TODO:CONFIG: allow auto configure for module
            # In this mode, whenever a new payload is sent, create a new connector
            # with the provided uuid, url and api_key
            _logger.warning(f"action:connector_not_found identifier:{identifier}")
            response = Response(json.dumps(
                {'message': 'Connector Not Found'}), status=404, content_type='application/json')
            return response
        try:
            incoming_payload = json.loads(http.request.httprequest.data)
        except json.decoder.JSONDecodeError:
            _logger.error(f"action:json_decode_error identifier:{identifier}, payload:{http.request.httprequest.data}")
            response = Response(json.dumps(
                {'message': 'Invalid JSON Payload'}), status=400, content_type='application/json')
            return response
        _logger.info(f"action incoming_payload connector {connector.id} payload {json.dumps(incoming_payload)}")
        response = connector.process_payload(incoming_payload)                
        return Response(json.dumps(response), headers={'Content-Type': 'application/json'})