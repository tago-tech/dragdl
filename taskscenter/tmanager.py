import os
import re
import json
import zipfile
import tarfile
from userapp.models import User
from taskscenter.models import Task
from taskscenter import tasks
from webserverDev import celery_app
from celery.utils.log import get_task_logger

logger = get_task_logger('workerslogger')

root = "./taskscenter/tlapp/"


path_models_pattern = root + "models/{}/{}"
path_metas_pattern = root + "metas/{}/{}"
path_logs_pattern = root + "logs/{}/{}"

path2meta = path_metas_pattern+"/meta.json"

#Task interfaces.
def CreateTask(user,meta):
    """
        Paramters:user instance.
        Paramters:meta data about task.
        Return:task instance id and status
    """

    logger.info("build on tl task,with meta data:{}.".format(meta))

    taskname = meta['taskname']


    taskname = meta['taskname']
    
    username = user.username 
    
    makeTaskSpace( username , taskname )
    
    saveMeta( username,taskname,meta )
    
    async_result = tasks.mockTask.delay(meta)

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

def startTask():
    pass

def listTasksCollection(user):
    pass

def QTask(tid):
    """
        Paramters:tid
        Return:infomation during model training.

        task state: [running | successful | failed];
            a. running:{ task_name,task_note,task_status , | ,metrics,epoch,dataset }
            b. successful:{ task_name,task_note,task_status , |,metrics,epoch,dataset }
            c. failed:{ task_name,task_note,task_status,task_error ,|,metrics,epoch,dataset,}
    """
    tasks_results = Task.objects.filter(id=tid)
    if not len(tasks_results):
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
    
    async_result = celery_app.AsyncResult(task_object.async_task_id)
    last_status = status2Map(async_result.status)
    if task_object.task_state not in ['TASK_SUCCESSFUL','TASK_FAILED']:
        task_object.task_state = last_status
        task_object.save()

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

def revokeTask(tid):
    pass

def stopTask(tid):
    pass

def rmTask(tid):
    pass

def basicForecast(path2PicStore,tid):
    
    tasks_results = Task.objects.filter(id=tid)
    
    task_object = tasks_results[0]
    
    path2Meta = task_object.task_meta

    async_result = None
    
    try:
        async_result = tasks.asyncPredict.delay([path2PicStore],path2Meta)
    except Exception as err:
        logger.error("faile to boot async predict task,for err:{} occured.".format(err))
    finally:
        os.remove(path2PicStore)

    while status2Map(async_result.status) in ['TASK_RUNNING','TASK_WAITING']:
        pass


    if status2Map(async_result.status) == "TASK_SUCCESSFUL":
        return async_result.result
    else:
        logger.error("fail to exec predict task,tid:{},err:{}".format(tid,async_result.info))
        return None

def syncForecast():
    pass

def asyncForecast():
    pass

def getTaskStatus(tid):
    pass

def updateTaskStatus(tid,status):
    pass

def logQTaskProcess(tobj):
    """
        Paramters:task instance-tobj
        Return:train process infomation on [train | dev | test] dataset.
    """
    process = {
            "train_loss":[],
            "train_acc":[],
            "dev_loss":[],
            "dev_acc":[],
            "test_loss":[],
            "test_acc":[]
    }
    path2CeleryLog = "./celery_worker.log"

    async_result_id = tobj.async_task_id
    
    path2ProcessInfo = tobj.async_log_path + '/process.json'

    if os.access(path2ProcessInfo,os.R_OK):
        with open(path2ProcessInfo,'r') as f:
            process =  json.load( f )
        return process
    
    if not os.access(path2CeleryLog,os.R_OK):
        raise IOError("fail to access celery worker logs file.")
        return process
    
    pattern_prefix = r'\['+async_result_id+r'\]: '
    pattern_train_step = pattern_prefix + 'step [0-9]{1,}: loss=(?P<train_loss>\d{1,}[\.]\d{1,}) acc=(?P<train_acc>\d{1,}[\.]\d{1,})'
    pattern_dev_step = pattern_prefix + r'\[dev dataset evaluation result\] loss=(?P<dev_loss>\d{1,}[\.]\d{1,}) acc=(?P<dev_acc>\d{1,}[\.]\d{1,})'
    pattern_test_step = pattern_prefix + r'\[test dataset evaluation result\] loss=(?P<test_loss>\d{1,}[\.]\d{1,}) acc=(?P<test_acc>\d{1,}[\.]\d{1,})'

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

    if tobj.task_state == 'TASK_SUCCESSFUL':
        with open(path2ProcessInfo,'w') as f:
            json.dump(process,f,indent=6)

    return process

def logQTaskException(tid):
    pass

# data interfaces
def makeTaskSpace(user_name,task_name):
    try:
        os.mkdir(path_models_pattern.format(user_name,task_name))
        os.mkdir(path_metas_pattern.format(user_name,task_name))
        os.mkdir(path_logs_pattern.format(user_name,task_name))
    except IOError as io_err:
        logger.error("fail to build user space,io_err={}".format(io_err))
        return False
    except Exception as err:
        logger.error("fail to build user space,err={}".format(err))
        return False
    return True

def saveMeta(user_name,task_name,data):
    with open(path2meta.format(user_name,task_name),'w') as f:
        json.dump(data,f,indent=4)
    return True

def status2Map(state):

    tstatusTable = {
        "PENDING":"TASK_WAITING",
        "STARTED":"TASK_RUNNING",
        "SUCCESS":"TASK_SUCCESSFUL",
        "FAILURE":"TASK_FAILED",
        "REVOKED":"TASK_WAITING"
    }
    if state not in tstatusTable:
        logger.warning("unknowen task state:{}".format(state))
        raise NameError("unknowen task state:{}".format(state))
    return tstatusTable[state]

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
            def is_within_directory(directory, target):
                
                abs_directory = os.path.abspath(directory)
                abs_target = os.path.abspath(target)
            
                prefix = os.path.commonprefix([abs_directory, abs_target])
                
                return prefix == abs_directory
            
            def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
            
                for member in tar.getmembers():
                    member_path = os.path.join(path, member.name)
                    if not is_within_directory(path, member_path):
                        raise Exception("Attempted Path Traversal in Tar File")
            
                tar.extractall(path, members, numeric_owner=numeric_owner) 
                
            
            safe_extract(tar, path=to_path)
    elif _is_targz(from_path):
        with tarfile.open(from_path, 'r:gz') as tar:
            def is_within_directory(directory, target):
                
                abs_directory = os.path.abspath(directory)
                abs_target = os.path.abspath(target)
            
                prefix = os.path.commonprefix([abs_directory, abs_target])
                
                return prefix == abs_directory
            
            def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
            
                for member in tar.getmembers():
                    member_path = os.path.join(path, member.name)
                    if not is_within_directory(path, member_path):
                        raise Exception("Attempted Path Traversal in Tar File")
            
                tar.extractall(path, members, numeric_owner=numeric_owner) 
                
            
            safe_extract(tar, path=to_path)
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

def userDataDetails(username,datasetname):
    res = {
        'cateigiesCount':[],
        'cateigiesName':[]
    }
    rootData = './taskscenter/tlapp/dlib/datas/{}/{}/'.format(username,datasetname)

    if not os.path.exists(rootData):
        return res
    cateigiesName = list(
        filter(
            lambda p: os.path.isdir(os.path.join(rootData, p)),
            os.listdir(rootData)
        )
    )
    cateigiesCount = []
    for cate in cateigiesName:
        cateigiesCount.append(len(list(os.listdir(os.path.join(rootData,cate)))))
    
    res['cateigiesCount'] = cateigiesCount
    res['cateigiesName'] = cateigiesName

    return res
