"""
    任务管理中心
        完成较为底层的任务操作,供 views 层调用
"""
# 对应包导入
import os
import re
import json
import zipfile
import tarfile
from userapp.models import User
from taskscenter.models import Task
from taskscenter import tasks
from webserverDev import celery_app

# worker文件根路径
root = "./taskscenter/tlapp/"


# 任务持久化空间路径集
path_models_pattern = root + "models/{}/{}"
path_metas_pattern = root + "metas/{}/{}"
path_logs_pattern = root + "logs/{}/{}"

#元数据文件存储路径
path2meta = path_metas_pattern+"/meta.json"

# < 任务 >相关接口
# 构建任务
def CreateTask(user,meta):
    """
        参数:用户数据库实例
        参数:meta数据
        return:任务数据库实例ID,状态
    """
    taskname = meta['taskname']

    # 元数据解析
    taskname = meta['taskname']
    username = user.username 
    # 创建任务空间
    makeTaskSpace( username , taskname )
    # 存储任务元数据
    saveMeta( username,taskname,meta )
    # 异步任务启动
    async_result = tasks.mockTask.delay(meta)
    # 任务数据库条目创建
    task_new_instance = {
            "task_name":taskname,
            "task_author":user,
            "task_meta":path2meta.format(username,taskname),
            "task_note":meta["tasknote"],
            "task_state": status2Map(async_result.status),
            "async_task_id":async_result.id,
            "async_model_path":path_models_pattern.format(username,taskname),
            "async_log_path":path_logs_pattern.format(username,taskname),
    }
    
    task_object = Task.objects.create(**task_new_instance)
    
    return task_object

# 启动任务
def startTask():
    """
        参数:meta
        return:异步结果
    """
    pass

# 当前用户下所zhuangtai有任务信息
def listTasksCollection(user):
    """
        参数:用户数据库实例
        return:任务信息集合
    """
    pass

# 查看任务
def QTask(tid):
    """
        参数:任务tid(数据库实例)
        return:任务多种信息

        任务三种状态: 运行中\成功结束\失败;
            a. 运行中返回:{ 任务名称,任务备注,任务状态 , | ,任务训练指标,任务Epoch,任务相关数据集 }
            b. 成功结束返回:{ 任务名称,任务备注,任务状态 , |,任务训练指标,任务Epoch,任务相关数据集 }
            c. 失败返回:{ 任务名称,任务备注,任务状态,任务错误信息 ,|,任务训练指标,任务Epoch,任务相关数据集 ,}
    """
    # 获取异步结果对应的数据库实例
    tasks_results = Task.objects.filter(id=tid)
    if not len(tasks_results):
        # 没有对应任务
        none_message = {
            "success":False,
            "id":"",
            "taskname":"",
            "status":"",
            "message":"No Task exists",
            "process":None
        }
        return none_message

    task_object = tasks_results[0]
    
    # 获取异步结果实例
    async_result = celery_app.AsyncResult(task_object.async_task_id)
    # 获取当前状态
    last_status = status2Map(async_result.status)
    # 更新当前状态
    if task_object.task_state not in ['TASK_SUCCESSFUL','TASK_FAILED']:
        task_object.task_state = last_status
        task_object.save()
    # 获取任务训练过程中指标信息
    processInfo = logQTaskProcess(task_object)

    query_respose = {
        "success":True,
        "id":async_result.id,
        "taskname":task_object.task_name,
        "status":task_object.task_state,
        "message":str(async_result.info),
        "process":processInfo
    }
    return query_respose

# 重启任务
def revokeTask(tid):
    pass

# 停止任务
def stopTask(tid):
    """
        参数:任务ID
        return:停止标志
    """
    pass

# 删除任务
def rmTask(tid):
    """
        参数:任务ID
        return:删除标志
    """
    # 任务状态判断

    # 停止任务
    
    pass

# 基础预测任务
def basicForecast(path2PicStore,tid):
    """
    """
    tasks_results = Task.objects.filter(id=tid)
    task_object = tasks_results[0]
    path2Meta = task_object.task_meta
    async_result = tasks.asyncPredict.delay([path2PicStore],path2Meta)
    #等待异步任务执行完成
    while status2Map(async_result.status) in ['TASK_RUNNING','TASK_WAITING']:
        pass
    #删除图片
    os.remove(path2PicStore)

    if status2Map(async_result.status) == "TASK_SUCCESSFUL":
        return async_result.result
    else:
        return None

# 同步预测任务
def syncForecast():
    """
        参数:
        return:
    """
    pass

# 异步预测任务
def asyncForecast():
    """
        参数:
        return:
    """
    pass

# 获取任务状态
def getTaskStatus(tid):
    """
        参数: 异步任务 id
        return: 异步任务状态
    """
    pass

# 更新任务状态
def updateTaskStatus(tid,status):
    """
        参数:任务id
        参数:最新任务状态
        return:更新成功标志
    """
    pass

# 日志查询-任务训练
def logQTaskProcess(tobj):
    """
        参数:任务实例对象tobj
        return:训练过程信息( 训练，测试，dev过程中误差和精度)
    """
    # 数据格式
    process = {
            "train_loss":[],
            "train_acc":[],
            "dev_loss":[],
            "dev_acc":[],
            "test_loss":[],
            "test_acc":[]
    }
    # celery整体worker的日志文件
    path2CeleryLog = "./celery_worker.log"
    # 获取数据库实例
    async_result_id = tobj.async_task_id
    path2ProcessInfo = tobj.async_log_path + '/process.json'

    # 如果存在直接可读
    if os.access(path2ProcessInfo,os.R_OK):
        with open(path2ProcessInfo,'r') as f:
            process =  json.load( f )
        return process
    
    # 判断文件可读
    if not os.access(path2CeleryLog,os.R_OK):
        raise IOError("糟了，读取不到celery_worker的日志!")
        return process
    
    # 模式串前缀,匹配特定异步任务
    pattern_prefix = r'\['+async_result_id+r'\]: '
    pattern_train_step = pattern_prefix + 'step [0-9]{1,}: loss=(?P<train_loss>\d{1,}[\.]\d{1,}) acc=(?P<train_acc>\d{1,}[\.]\d{1,})'
    pattern_dev_step = pattern_prefix + r'\[dev dataset evaluation result\] loss=(?P<dev_loss>\d{1,}[\.]\d{1,}) acc=(?P<dev_acc>\d{1,}[\.]\d{1,})'
    pattern_test_step = pattern_prefix + r'\[test dataset evaluation result\] loss=(?P<test_loss>\d{1,}[\.]\d{1,}) acc=(?P<test_acc>\d{1,}[\.]\d{1,})'
    # 正则匹配过程
    with open(path2CeleryLog,'r') as f:
        lines = f.readlines()
        for line in lines:            
            step_train_re = re.search(pattern_train_step,line)
            if step_train_re:
                group_dict = step_train_re.groupdict()
                process['train_loss'].append(float(group_dict['train_loss']))
                process['train_acc'].append(float(group_dict['train_acc']))
                continue
            
            step_dev_re = re.search(pattern_dev_step,line)
            if step_dev_re:
                group_dict = step_dev_re.groupdict()
                process['dev_loss'].append(float(group_dict['dev_loss']))
                process['dev_acc'].append(float(group_dict['dev_acc']))
                continue
            
            step_test_re = re.search(pattern_test_step,line)
            if step_test_re:
                group_dict = step_test_re.groupdict()
                process['test_loss'].append(float(group_dict['test_loss']))
                process['test_acc'].append(float(group_dict['test_acc']))

    # if task successful
    # 持久化(选择持久化的时机),影响后续判断是否直接从文件读取
    if tobj.task_state == 'TASK_SUCCESSFUL':
        with open(path2ProcessInfo,'w') as f:
            json.dump(process,f,indent=6)

    return process

# 日志查询-任务异常
def logQTaskException(tid):
    pass

# 创建任务空间
def makeTaskSpace(user_name,task_name):
    # 模型目录
    os.mkdir(path_models_pattern.format(user_name,task_name))
    # 元数据目录
    os.mkdir(path_metas_pattern.format(user_name,task_name))
    # 日志目录
    os.mkdir(path_logs_pattern.format(user_name,task_name))

    return True

# 保存meta数据
def saveMeta(user_name,task_name,data):
    with open(path2meta.format(user_name,task_name),'w') as f:
        json.dump(data,f,indent=4)
    return True

# 异步任务状态转换
def status2Map(state):
    # 任务状态对应表
    tstatusTable = {
        "PENDING":"TASK_WAITING",
        "STARTED":"TASK_RUNNING",
        "SUCCESS":"TASK_SUCCESSFUL",
        "FAILURE":"TASK_FAILED",
        "REVOKED":"TASK_WAITING"
    }
    if state not in tstatusTable:
        print("未知状态:{}".format(state))
        raise NameError("任务状态未知")
    return tstatusTable[state]

#< 数据 > 相关接口
def _is_tar(filename):
    return filename.endswith(".tar")


def _is_targz(filename):
    return filename.endswith(".tar.gz")


def _is_gzip(filename):
    return filename.endswith(".gz") and not filename.endswith(".tar.gz")


def _is_zip(filename):
    return filename.endswith(".zip")

def extract_archive(from_path, to_path=None, remove_finished=False):
    if to_path is None:
        to_path = os.path.dirname(from_path)

    if _is_tar(from_path):
        with tarfile.open(from_path, 'r') as tar:
            tar.extractall(path=to_path)
    elif _is_targz(from_path):
        with tarfile.open(from_path, 'r:gz') as tar:
            tar.extractall(path=to_path)
    elif _is_gzip(from_path):
        to_path = os.path.join(to_path, os.path.splitext(os.path.basename(from_path))[0])
        with open(to_path, "wb") as out_f, gzip.GzipFile(from_path) as zip_f:
            out_f.write(zip_f.read())
    elif _is_zip(from_path):
        with zipfile.ZipFile(from_path, 'r') as z:
            z.extractall(to_path)
    else:
        raise ValueError("Extraction of {} not supported".format(from_path))

    if remove_finished:
        os.remove(from_path)

#查看某一数据集详情
def userDataDetails(username,datasetname):
    #返回信息的格式
    res = {
        'cateigiesCount':[],
        'cateigiesName':[]
    }
    #数据集的目录
    rootData = './taskscenter/tlapp/dlib/datas/{}/{}/'.format(username,datasetname)

    if not os.path.exists(rootData):
        return res
    #分类名称
    cateigiesName = list(
        filter(
            lambda p: os.path.isdir(os.path.join(rootData, p)),
            os.listdir(rootData)
        )
    )
    #各分类数目
    cateigiesCount = []
    for cate in cateigiesName:
        cateigiesCount.append(len(list(os.listdir(os.path.join(rootData,cate)))))
    
    res['cateigiesCount'] = cateigiesCount
    res['cateigiesName'] = cateigiesName

    return res