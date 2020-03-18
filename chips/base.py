# -*- coding: utf-8 -*-

import cherrypy
import os
import logging
from cherrypy import _cpconfig


def daemonize(user, group, pidfile=None):
    if os.name == 'posix' and os.getuid() == 0:
        from cherrypy.process.plugins import DropPrivileges
        import grp
        import pwd
        try:
            uid = pwd.getpwnam(user)[2]
            gid = grp.getgrnam(group)[2]
        except KeyError:
            cherrypy.log.error(
                'Cannot find user `{0}` or group `{1}`'.format(user, group),
                'DAEMONIZE',
                logging.FATAL
            )
            raise
        cherrypy.drop_privileges = DropPrivileges(
            cherrypy.engine, uid=uid, gid=gid).subscribe()
    
    from cherrypy.process.plugins import PIDFile, Daemonizer
    if pidfile:
        PIDFile(cherrypy.engine, pidfile).subscribe()
    Daemonizer(cherrypy.engine).subscribe()
    

class _Stub:
    pass


class AppTree:
    '''
    Дерево приложения(приложений)
    '''

    def __init__(self, stub_factory=_Stub):
        self.stub_factory = stub_factory
        self.clear()

    def clear(self):
        self.root = None

    def _handler_exists(self, path_list):
        if not path_list:
            return bool(self.root)
        current = self.root
        for element in path_list:
            try:
                current = getattr(current, element)
            except AttributeError:
                return False
        return True

    def _find_owner(self, path_list):
        if not path_list and not self.root:
            self.root = self.stub_factory()
        result = self.root
        for element in path_list:
            if not hasattr(result, element):
                setattr(result, element, self.stub_factory())
            result = getattr(result, element)
        return result

    def add(self, path, handler, config=None):
        stripped_path = path.strip('/')
        path_list = stripped_path.split('/') if stripped_path else []

        if self._handler_exists(path_list):
            raise AttributeError('Path `%s` is busy' % path)

        if config:
            if not hasattr(handler, '_cp_config'):
                handler._cp_config = {}
            _cpconfig.merge(handler._cp_config, config)

        handler._cp_mount_path = '/' + stripped_path
        if not path_list:
            self.root = handler
        else:
            setattr(self._find_owner(path_list[0:-1]), path_list[-1], handler)
        cherrypy.log.error('%s mounted on `%s`' % (type(handler).__name__, path), 'TREE')


