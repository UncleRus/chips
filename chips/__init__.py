# -*- coding: utf-8 -*-

__version__ = '1.0'

import cherrypy
from . import base, rpc, plugins, jinja

# Basic
from .base import AppTree, daemonize

# Plugins
cherrypy.engine.bg_tasks_queue = plugins.TasksQueue(cherrypy.engine)
cherrypy.engine.task_manager = plugins.TaskManager(cherrypy.engine)
cherrypy.engine.starter_stopper = plugins.StarterStopper(cherrypy.engine)

# Tools
cherrypy.tools.jinja = jinja.JinjaTool()
