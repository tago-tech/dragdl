"""
    用户管理中心
        完成杂乱的用户管理任务
"""
import os
root = "./taskscenter/tlapp/"
path_models_pattern = root + "models/{}"
path_datasets_pattern = root + "dlib/datas/{}"
path_metas_pattern = root + "metas/{}"
path_logs_pattern = root + "logs/{}"

# 创建用户目录
def makeUserSpace(name):
    # 模型目录
    os.mkdir(path_models_pattern.format(name))
    # 数据目录
    os.mkdir(path_datasets_pattern.format(name))
    # 元数据目录
    os.mkdir(path_metas_pattern.format(name))
    # 日志目录
    os.mkdir(path_logs_pattern.format(name))
    
    return True

# 删除用户目录
def rmUserSpace(name):
    pass






