# -*- coding: utf-8 -*-

import json
import logging
import concurrent.futures
import time
import cherrypy
import typing

from . import config
from . import jsonrpc


def expose(entity):
    entity.__rpc_exposed = True
    return entity


def atomic(entity):
    entity.__rpc_atomic = True
    return entity


# Конфигурация по умолчанию
_jsonrpc_conf = config.Namespace('jsonrpc', {
    'encoding': 'utf-8',
    'threaded_batch': True,  # Выполнять батч-запросы в параллельных потоках
    'batch_threads_max': 10,  # Максимум одновременно порождаемых потоков на один батч
    'batch_timeout': 600,  # 10 минут по умолчанию
})


def _no_request_processing_tool():
    '''Инструмент для отключения обработки содержимого POST'''
    if cherrypy.request.method == 'POST':
        cherrypy.request.body.processors = {}


# Создаем экземпляр инструмента для отключения обработки POST
cherrypy.tools.no_request_procesing = cherrypy.Tool(
    "on_start_resource", _no_request_processing_tool)


class RootController:
    '''
    Базовый класс корневых контроллеров JSON-RPC 2.0
    '''

    def _find_method(self, name):
        '''
        Поиск метода по имени в контроллере
        '''
        result = self
        for attr in str(name).split('.'):
            result = getattr(result, attr, None)
            if not result:
                return None
        return result if getattr(result, '__rpc_exposed', False) else None

    def _exec_single(self, req: typing.Union[jsonrpc.SingleRequest, jsonrpc.Error]):
        '''
        Выполнение единичного метода в текущем потоке
        req - jsonrpc.SingleRequest или jsonrpc.Error
        '''
        if isinstance(req, jsonrpc.Error):
            cherrypy.log('Could not parse JSON request',
                         'RPC', severity=logging.ERROR)
            return req

        cherrypy.log('call (id={}) "{}"'.format(req.rpc_id, req.method),
                     'RPC', severity=logging.DEBUG)

        method = self._find_method(req.method)
        if not method:
            cherrypy.log('Method "{}" not found (id={})'.format(req.method, req.rpc_id),
                         'RPC', severity=logging.ERROR)
            if req.rpc_id is not None:
                return jsonrpc.Error(req.rpc_id,
                                     code=jsonrpc.Error.METHOD_NOT_FOUND)
            return None

        if req.rpc_id is None:
            # Это просто Notification, выполняем его, ответа и сообщений об ошибках быть не должно
            try:
                method(*req.args, **req.kwargs)
            except:
                cherrypy.log('Error while executing notification handler "{}" (id={})'.format(req.method, req.rpc_id),
                             'RPC', severity=logging.ERROR, traceback=True)
            return None

        try:
            # Выполняем метод
            res = method(*req.args, **req.kwargs)
            return res if req.rpc_id is not None else None
        except Exception as e:
            cherrypy.log('Error while executing method handler "{}" (id={})'.format(req.method, req.rpc_id),
                         'RPC', severity=logging.ERROR, traceback=True)
            if isinstance(e, jsonrpc.Error):
                return e
            else:
                return jsonrpc.Error(req.rpc_id,
                                     message=str(e),
                                     code=jsonrpc.Error.GENERIC_APPLICATION_ERROR,
                                     data=repr(e))

    def _exec_batch(self, request: jsonrpc.BatchRequest):
        '''
        Выполнение батч-запроса
        '''
        def wrapper(request):
            cherrypy.engine.publish('acquire_thread')
            try:
                res = self._exec_single(request)
            finally:
                cherrypy.engine.publish('release_thread')
            return res

        res = []  # Результат
        single = []  # Запросы для исполнения в текщем потоке
        batch = []  # Запрос для исполнения в раздельных потоках

        if not _jsonrpc_conf.threaded_batch:
            # Если отключена опция выполнения батча в разных потоках,
            # то он весь будет исполнен в текущем последовательно
            single = request
        else:
            # Разбираем батч
            for r in request.requests:
                if isinstance(r, jsonrpc.Error):
                    # Это ошибка парсинга, отправляем ее в результат напрямую
                    res.append(r)
                    continue
                if getattr(self._find_method(r.method), '__rpc_atomic', False):
                    # У найденного метода есть флаг атомарного выполнения, в текущий поток его
                    single.append(r)
                    continue
                # По умолчанию в мультитредовый
                batch.append(r)

        if batch:
            # У нас есть что выполнить в разных тредах
            f = []  # выполняющиеся запросы
            r = []  # завершенные запросы

            with concurrent.futures.ThreadPoolExecutor(max_workers=_jsonrpc_conf.batch_threads_max,
                                                       thread_name_prefix='json_rpc_batch_') as pool:
                # отправляем все запросы в параллельные потоки, обертывая каждый во wrapper()
                # сохраняем tuple(request, future) в список выполняющихся
                for req in batch:
                    f.append((req, pool.submit(wrapper, req)))

                # ждем, пока все запросы не будут завершены
                stime = time.time()
                etime = stime + _jsonrpc_conf.batch_timeout
                while f:
                    r.extend(filter(lambda x: x[1].done(), f))
                    f[:] = filter(lambda x: not x[1].done(), f)
                    if time.time() >= etime:
                        cherrypy.log('Timeout while batch-executing: %d threads still running' %
                                     len(f), 'RPC', severity=logging.ERROR)
                        break
                    if f:
                        time.sleep(0.1)

                # Собираем результаты
                for req, future in r:
                    if req.rpc_id is None:
                        # Это notification, результат не нужен
                        continue
                    fr = future.result()
                    if isinstance(fr, jsonrpc.Error):
                        fr.rpc_id = req.rpc_id  # перезаписываем на всякий случай rpc_id
                        res.append(fr)
                    else:
                        res.append((req.rpc_id, fr))

                for req, _ in f:
                    # По всем зависшим запросам отдается таймаут
                    res.append(jsonrpc.Error(
                        req.rpc_id, code=jsonrpc.Error.TIMEOUT))

                pool.shutdown(False)

        # Выполняем все однопоточные запросы
        for r in single:
            res.append(self._exec_single(r))

        return res

    @cherrypy.expose
    @cherrypy.tools.no_request_procesing()
    def default(self, *_vpath, **_params):
        '''
        Обработчик по умолчанию
        '''
        # парсим реквест
        req = jsonrpc.parse_request(
            cherrypy.request.body.fp, _jsonrpc_conf.encoding)

        if isinstance(req, jsonrpc.BatchRequest):
            # Ставим на выполнение пачку и ждем, пока они не выполнятся
            resp = jsonrpc.batch_result(self._exec_batch(req))
        else:
            # В основном потоке выполняем метод
            resp = jsonrpc.single_result(
                req.rpc_id, self._exec_single(req))

        response = cherrypy.response
        response.status = '200 OK'
        if resp is not None:
            response.body = json.dumps(resp).encode(_jsonrpc_conf.encoding)
            response.headers['Content-Type'] = 'text/json; charset=%s' % _jsonrpc_conf.encoding
            response.headers['Content-Length'] = len(response.body)
        else:
            response.body = b''

        return response.body
