#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# Author:tangsz
from __future__ import absolute_import, unicode_literals
import os
from celery import Celery


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webserverDev.settings')  # 设置django环境

app = Celery('webServerDev')

app.config_from_object('django.conf:settings', namespace='CELERY') #  使用CELERY_ 作为前缀，在settings中写配置

#Configure tasks Auto-dicover
app.autodiscover_tasks()  