import os
import json
import random
from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
# 用户校验
from userapp.token import verify_token,tokenUserInfo,userInfoCheck
from userapp.models import User
from userapp.serializers import  UserSerializer
# 异步任务
from webserverDev import celery_app
from taskscenter import tasks
from taskscenter.models import Task
from taskscenter.serializers import TaskSerializer
from taskscenter import tmanager

# Create your views here.
class TasksViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    queryset = Task.objects.all()

    # 构建并启动任务
    @action(detail=False, methods=['post'])
    def buildtask(self,request):
        """
                建立一个任务并执行

                # 用户验证
                # 异常检查
                # 结果回传
        """
        res = {
                "success":False,
                "message":"登录要求(权限问题)"
        }
        # 用户验证
        online_who = userInfoCheck(request)
        if( online_who == 'guest'):
            # 登陆要求
            return Response(res)
        else:
            # IO异常 , 任务创建异常，数据库异常
            try:
                res['message'] = "权限验证通过，未解析中"
                data = json.loads(request.body)
                print("Server 收到 请求:{}".format(data))

                meta = json.loads(request.body)
                # 用户索引
                user = User.objects.filter(username=meta['username'])[0]
                # 任务数据库实例
                task_object = tmanager.CreateTask(user,meta)

                res["message"] = "构建任务成功"
                res["success"] = True
                res["TaskId"] = task_object.id

            except IOError:
                print(" IO 错误 !")
            finally:
                return Response(res)
        
        # tasks.mul.delay(2,3)

    # 查看指定任务详情(运行中、失败、成功)
    @action(detail=False,methods=['post'])
    def lookTask(self,request):
        data = json.loads(request.body)
        print(data)
        reponse = tmanager.QTask(data['tid'])
        return Response( reponse )

    # 查看用户下任务集
    @action(detail=False,methods=['post'])
    def listUserTasks(self,request):
        
        online_who = userInfoCheck(request)
        print('[listUserTasks]当前用户:'+online_who)
        data = json.loads(request.body)
        res = {
            'successful':False,
            'message':'',
            'username':data['username'],
            'taskInfos':[]
        }
        if not len(User.objects.filter(username=data['username'])):
            res['message'] = '用户不存在'
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

    # 重启任务
    def editTask(self,request):
        pass
    
    # 删除任务
    def removeTask(self,request):
        pass

    # 暂停任务
    def stopTask(self,request):
        pass

    # 预测任务
    @action(detail=False,methods=['post'])
    def predict(self,request):
        #相应格式
        res = {
            'successful':False,
            'picName':'',
            'result':'',
            'info':{
                'cateigies':[],
                'scores':[]
            }
        }
        # 获取相关的 task id
        tid = request.data['tid']

        #获取提交的图片
        fileInstance = request.FILES.get('file')
        storeKey = 'CacheP{}_{}'.format(random.random(),fileInstance.name)
        path2PicStore = './taskscenter/tlapp/dlib/datas/Caches/{}'.format(storeKey)
        #存入图片
        with open(path2PicStore,'wb')  as f:
            for fileChunk in fileInstance.chunks():
                f.write(fileChunk)

        result = tmanager.basicForecast(path2PicStore,tid)

        if result is not None:
            res['picName'] = fileInstance.name
            res['result'] = result['result'].split('#')[0]
            res['info']['cateigies'] = result['classes']
            res['info']['scores'] = result['socres']
        print('预测结果:{}'.format(res))
        return Response(res)

    # 测试 get \ post \ 用户检查 方法
    @action(detail=False,methods=['post'])
    def invokeAsync(self,request):
        # 测试数据
        meta = json.loads(request.body)

        # 用户索引
        user = User.objects.filter(username=meta['username'])[0]
        # 任务数据库实例
        task_object = tmanager.CreateTask(user,meta)

        return Response({"successful":True,"message":"新建任务成功","TaskId":task_object.id})
    
    ###
        数据相关操作
    ###
    #上传并解压缩用户数据集
    @action(detail=False,methods=['post'])
    def addDatafile(self,request):
        res = {
            'successful':False,
            'message':'accept'
        }
        #获取当前登录用户
        username = userInfoCheck(request)
        #计算写入的目录
        fileInstance = request.FILES.get('file')
        path2Store = './taskscenter/tlapp/dlib/datas/Caches/{}'.format(fileInstance.name)
        with open(path2Store,'wb') as f:
            for fileChunk in fileInstance.chunks():
                f.write(fileChunk)
        #解压缩
        pathUNZIP = './taskscenter/tlapp/dlib/datas/{}/'.format(username)
        tmanager.extract_archive(path2Store,pathUNZIP,True)
        return Response(res)

    #查看用户所有数据集列表
    @action(detail=False,methods=['post'])
    def listUserDatas(self,request):
        #响应格式
        res = {
            'successful':False,
            'datasetsName':[],
            'datasinfo':[]
        }
        #用户信息
        username = userInfoCheck(request)
        #用户数据集主目录
        rootData = './taskscenter/tlapp/dlib/datas/{}/'.format(username)
        if not os.path.exists(rootData):
            return Response(res)
        #数据集名称集合
        datasetsName = list(
            filter(
                lambda p: os.path.isdir(os.path.join(rootData, p)),
                os.listdir(rootData)
            )
        )
        #统计各数据集信息
        datasinfo = []
        for dataItem in datasetsName:
            datasinfo.append(tmanager.userDataDetails(username,dataItem))
        
        res['successful'] = True
        res['datasetsName'] = datasetsName
        res['datasinfo'] = datasinfo

        return Response(res)

    @action(detail=False,methods=['post'])
    def userScence(self,request):
        
        username = userInfoCheck(request)
        userMenuJson = None
        with open('./taskscenter/tlapp/apiDemo.json','r') as f:
            userMenuJson = json.load(f)
        
        #用户数据集主目录
        rootData = './taskscenter/tlapp/dlib/datas/{}/'.format(username)
        
        if not os.path.exists(rootData):
            return Response(userMenuJson)

        #数据集名称集合
        datasetsName = list(
            filter(
                lambda p: os.path.isdir(os.path.join(rootData, p)),
                os.listdir(rootData)
            )
        )
        #统计各数据集信息
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

    


