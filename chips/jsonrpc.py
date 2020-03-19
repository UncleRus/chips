# -*- coding: utf-8 -*-

import json


class JsonRpcException(Exception):

    USER_ERROR = -32100
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    GENERIC_APPLICATION_ERROR = -32000
    TIMEOUT = -32001

    messages = {
        PARSE_ERROR: 'Parse Error',
        INVALID_REQUEST: 'Invalid Request',
        METHOD_NOT_FOUND: 'Method Not Found',
        INVALID_PARAMS: 'Invalid Parameters',
        INTERNAL_ERROR: 'Internal Error',
        GENERIC_APPLICATION_ERROR: 'Application Error',
        TIMEOUT: 'Timeout',
    }

    def __init__(self, rpc_id, code=None, message=None, data=None):
        self.rpc_id = rpc_id
        self.code = code or self.USER_ERROR
        self.message = message or self.messages.get(code, 'Unknown Error')
        self.data = data

    def as_dict(self):
        res = {
            'jsonrpc': '2.0',
            'id': self.rpc_id,
            'error': {
                'code': self.code,
                'message': self.message,
            }
        }
        if self.data:
            res['error']['data'] = self.data
        return res

    def __str__(self):
        return json.dumps(self.as_dict())

    def __repr__(self):
        return 'JsonRpcException<id=%r, code=%r, message=%r>' % (self.rpc_id, self.code, self.message)


class JsonRpcSingleRequest:

    def __init__(self, data):
        if not isinstance(data, dict):
            raise JsonRpcException(None, code=JsonRpcException.INVALID_REQUEST)
        self.data = data

        self.rpc_id = self.data.get('id')

        if self.data.get('jsonrpc') != '2.0':
            raise JsonRpcException(
                self.rpc_id, code=JsonRpcException.INVALID_REQUEST)

        self.method = self.data.get('method')
        if not isinstance(self.method, str) or not self.method:
            raise JsonRpcException(
                self.rpc_id, code=JsonRpcException.INVALID_REQUEST)

        self.params = self.data.get('params', [])
        if not isinstance(self.params, (list, dict)):
            raise JsonRpcException(
                self.rpc_id, code=JsonRpcException.INVALID_PARAMS)

        if isinstance(self.params, list):
            self.args = self.params
            self.kwargs = {}
        else:
            self.args = []
            self.kwargs = self.params


class JsonRpcBatchRequest:

    def __init__(self, data):
        if not isinstance(data, list):
            raise JsonRpcException(None, code=JsonRpcException.INVALID_REQUEST)
        self.data = data

        self.requests = []
        for req in self.data:
            try:
                self.requests.append(JsonRpcSingleRequest(req))
            except JsonRpcException as e:
                self.requests.append(e)


def parse_request(raw, encoding='utf-8'):
    try:
        if isinstance(raw, (bytes, bytearray, str)):
            data = json.loads(raw, encoding=encoding)
        else:
            data = json.load(raw)
    except Exception as e:
        return JsonRpcException(None, code=JsonRpcException.INVALID_REQUEST, data=str(e))
    if isinstance(data, list):
        return JsonRpcBatchRequest(data)
    else:
        return JsonRpcSingleRequest(data)


def single_result(rpc_id, r):
    if rpc_id is None:
        return None
    if isinstance(r, JsonRpcException):
        return r.as_dict()
    return {
        'jsonrpc': '2.0',
        'id': rpc_id,
        'result': r
    }


def batch_result(r):
    '''
    r -> [(<rpc_id>, <result>) | JsonRpcException(), ...]
    e.g.
    [(1, 10000), JsonRpcException(2, code=GENERIC_APPLICATION_ERROR), (3, ['some', 'result']), ...]
    '''
    if not isinstance(r, (list, tuple)):
        return JsonRpcException(None, code=JsonRpcException.INTERNAL_ERROR, data='Invalid response').as_dict()

    res = []
    try:
        for item in r:
            if item is None:
                continue
            if not isinstance(item, (tuple, list, JsonRpcException)):
                raise Exception('Invalid response item')
            if isinstance(item, JsonRpcException):
                res.append(single_result(item.rpc_id, item))
            else:
                res.append(single_result(*item))
        return res
    except Exception as e:
        return JsonRpcException(None, code=JsonRpcException.INTERNAL_ERROR, data=str(e)).as_dict()
