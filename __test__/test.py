#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cherrypy
import logging
from chips import rpc


class Test:

    @rpc.expose
    def hello(self, who):
        return 'Hello %s!' % who

    @rpc.expose
    def test_div(self, arg1, arg2):
        return arg1 / arg2


class Volatile:

    def __init__(self, param):
        self.param = param

    @rpc.expose
    def test(self, arg1, arg2):
        return arg1 + arg2 if self.param == 'add' else arg1 - arg2


class Root(rpc.RootController):

    def __init__(self):
        self.test = Test()
        self.vadd = Volatile('add')
        self.vsub = Volatile('sub')


if __name__ == '__main__':
    app = cherrypy.tree.mount(Root(), '')

    app.log.error_log.setLevel(logging.DEBUG)

    cherrypy.engine.signals.subscribe()
    cherrypy.engine.start()
    cherrypy.engine.block()
