from __future__ import absolute_import, unicode_literals
from celery import shared_task
# from celery.utils.log import get_task_logger
from celery.utils.log import get_task_logger
# 模拟测试任务

from .tlapp.start import parse_and_train,parse_and_predict

logger = get_task_logger('workerslogger')


@shared_task
def add(x, y):
    return x + y

@shared_task
def mul(x, y):
    logger.info('[]( {} * {} = {})'.format(x,y,x*y))
    return x * y

# 模拟任务
@shared_task(track_started=True)
def mockTask(meta):
    """
            训练任务
    """
    # 传递任务
    parse_and_train(meta,logger)

# 预测任务
@shared_task(track_started=True)
def asyncPredict(data,path2Meta):
    return parse_and_predict(data,path2Meta,logger)
