import os
import json
import random
from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
# user token control
from userapp.token import verify_token,tokenUserInfo,userInfoCheck
from userapp.models import User
from userapp.serializers import  UserSerializer
# async task control
from webserverDev import celery_app
from taskscenter import tasks
from taskscenter.models import Task
from taskscenter.serializers import TaskSerializer
from taskscenter import tmanager
# log moudle
from celery.utils.log import get_task_logger

logger = get_task_logger('workerslogger')

class TasksViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    queryset = Task.objects.all()

    # build and boot task.
    @action(detail=False, methods=['post'])
    def buildtask(self,request):
        """
            Set up a task and execute it
            1.authentication
            2.execption
            3.return results
        """
        res = {
                "success":False,
                "message":"Authority issues."
        }
        # authentication
        online_who = userInfoCheck(request)
        if( online_who == 'guest'):
            return Response(res)
        else:

            try:
                res['message'] = "permission verification passed."
                data = json.loads(request.body)
                logger.info("server recieve request:{}".format(data))

                meta = json.loads(request.body)
                
                user = User.objects.filter(username=meta['username'])[0]

                task_object = tmanager.CreateTask(user,meta)

                res["message"] = "build task successful."
                res["success"] = True
                res["TaskId"] = task_object.id

            except IOError as io_err:
                logger.error("Fail to build task ,for IOExecption Occur:{}".format(io_err))
            finally:
                return Response(res)
        
    # query task instance.
    @action(detail=False,methods=['post'])
    def lookTask(self,request):
        data = json.loads(request.body)        
        reponse = tmanager.QTask(data['tid'])
        return Response( reponse )

    # query user datasets.
    @action(detail=False,methods=['post'])
    def listUserTasks(self,request):
        
        online_who = userInfoCheck(request)
        print('[listUserTasks]Current user:'+online_who)
        data = json.loads(request.body)
        res = {
            'successful':False,
            'message':'',
            'username':data['username'],
            'taskInfos':[]
        }
        if not len(User.objects.filter(username=data['username'])):
            res['message'] = 'user does not exist'
            return Response(res)  
        user = User.objects.filter(username=data['username'])[0]
        tasksObjs = Task.objects.filter(task_author=user)
        for taskItem in tasksObjs:
            res['taskInfos'].append(
                {
                    'appid':taskItem.id,
                    'appname':taskItem.task_name,
                    'appnote':taskItem.task_note,
                    'appstate':taskItem.task_state,
                    'buildtime':taskItem.build_time
                }
            )
        res['taskInfos'].reverse()
        res['successful'] = True
        return Response(res)

    # revoker task.
    def editTask(self,request):
        pass
    
    # remove task.
    def removeTask(self,request):
        pass

    # pause task.
    def stopTask(self,request):
        pass

    # sync predict task.
    @action(detail=False,methods=['post'])
    def predict(self,request):
        res = {
            'successful':False,
            'picName':'',
            'result':'',
            'info':{
                'cateigies':[],
                'scores':[]
            }
        }
        tid = request.data['tid']

        fileInstance = request.FILES.get('file')
        storeKey = 'CacheP{}_{}'.format(random.random(),fileInstance.name)
        path2PicStore = './taskscenter/tlapp/dlib/datas/Caches/{}'.format(storeKey)
        
        with open(path2PicStore,'wb')  as f:
            for fileChunk in fileInstance.chunks():
                f.write(fileChunk)

        result = tmanager.basicForecast(path2PicStore,tid)

        

        if result is not None:
            res['picName'] = fileInstance.name
            res['result'] = result['result'].split('#')[0]
            res['info']['cateigies'] = result['classes']
            res['info']['scores'] = result['socres']
        
        logger.info("Prediction:{}".format(res))
        
        res['successful'] = True

        return Response(res)

    @action(detail=False,methods=['post'])
    def invokeAsync(self,request):

        meta = json.loads(request.body)

        user = User.objects.filter(username=meta['username'])[0]

        task_object = tmanager.CreateTask(user,meta)

        return Response({"successful":True,"message":"New task successfully created","TaskId":task_object.id})
    
    #Data interfaces
    #Upload and decompress user datasets
    @action(detail=False,methods=['post'])
    def addDatafile(self,request):
        res = {
            'successful':False,
            'message':'accept'
        }
        #Get current login user
        username = userInfoCheck(request)

        fileInstance = request.FILES.get('file')
        logger.info("Upload and decompress user datasets [{}]".format(fileInstance))

        path2Store = './taskscenter/tlapp/dlib/datas/Caches/{}'.format(fileInstance.name)
        with open(path2Store,'wb') as f:
            for fileChunk in fileInstance.chunks():
                logger.info('{} write {}...'.format(fileInstance.name,path2Store))
                f.write(fileChunk)
        pathUNZIP = './taskscenter/tlapp/dlib/datas/{}/'.format(username)
        tmanager.extract_archive(path2Store,pathUNZIP,True)
        return Response(res)

    #View a list of all user datasets
    @action(detail=False,methods=['post'])
    def listUserDatas(self,request):
        res = {
            'successful':False,
            'datasetsName':[],
            'datasinfo':[]
        }
        username = userInfoCheck(request)
        logger.info('[listUserDatas]Current user:{}'.format(username))
        rootData = './taskscenter/tlapp/dlib/datas/{}/'.format(username)
        
        if not os.path.exists(rootData):
            return Response(res)

        datasetsName = list(
            filter(
                lambda p: os.path.isdir(os.path.join(rootData, p)),
                os.listdir(rootData)
            )
        )
        datasinfo = []
        for dataItem in datasetsName:
            datasinfo.append(tmanager.userDataDetails(username,dataItem))
        
        res['successful'] = True
        res['datasetsName'] = datasetsName
        res['datasinfo'] = datasinfo

        logger.info('[listUserDatas] return {}'.format(res))
        
        return Response(res)

    @action(detail=False,methods=['post'])
    def userScence(self,request):
        
        username = userInfoCheck(request)
        logger.info('[userSencen]Current user:{}'.format(username))

        userMenuJson = None
        
        with open('./taskscenter/tlapp/apiDemo.json','r') as f:
            userMenuJson = json.load(f)
        
        rootData = './taskscenter/tlapp/dlib/datas/{}/'.format(username)
        
        if not os.path.exists(rootData):
            return Response(userMenuJson)

        datasetsName = list(
            filter(
                lambda p: os.path.isdir(os.path.join(rootData, p)),
                os.listdir(rootData)
            )
        )
        datasinfo = []
        for dataItem in datasetsName:
            datasinfo.append(len(tmanager.userDataDetails(username,dataItem)['cateigiesName']))
        for index in range(len(datasinfo)):
            dsItem = {
                "name":datasetsName[index],
                "type":"DataSet",
                "shapeUI":"u0d1",
                "num_class":datasinfo[index],
                "train":8,
                "dev":1,
                "test":1
            }
            userMenuJson.append(dsItem)
        return Response(userMenuJson)

    



