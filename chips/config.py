# -*- coding: utf-8 -*-

import cherrypy


class Namespace(object):
    '''
    Класс-утилита для чтения конфигурации
    '''

    __exit__ = None

    def __init__(self, name, defaults=None):
        '''
        Конструктор. Привязывает пространство имен к конфигурации CherryPy по умолчанию.

        :param name: Название пространства имен
        :param defaults: Значения параметров конфигурации по умолчанию
        '''
        self.config = defaults or {}
        cherrypy.config.namespaces[name] = self

    def __call__(self, key, value):
        self.config[key] = value

    def __getattr__(self, name):
        return self.config[name]

    def __getitem__(self, name):
        return self.config[name]
