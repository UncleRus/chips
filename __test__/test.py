#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cherrypy
from chips import rpc


class Test:

    @rpc.expose
    def hello(self, who):
        return 'Hello %s!' % who


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
    cherrypy.quickstart(Root(), '')
