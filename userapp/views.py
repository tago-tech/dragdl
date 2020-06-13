import os
from django.shortcuts import render
from userapp.models import User
from django.http import HttpResponse
import json
from rest_framework import viewsets
from rest_framework.response import Response
# from rest_framework.decorators import list_route
from django.contrib.auth.hashers import make_password,check_password
from userapp.serializers import UserSerializer
from userapp.token import create_token,verify_token,tokenUserInfo
from rest_framework.decorators import action

from userapp.umanager import makeUserSpace

# Create your views here.
class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all()

    # User registration
    @action(detail=False, methods=['post'])
    def register(self,request):
        data = json.loads(request.body)
        user = User.objects.filter(username=data['username'])
        if len(user):
            res = {
                'success':False,
                'mess':'User name registered'
            }
            return Response(res)
        data['password'] = make_password(data['password'])
        # Create user database instance
        user_object = User.objects.create(**data)
        # Create user space
        makeUserSpace(user_object.username)

        if user_object:
            res = {
                    'success':True,
                    'mess':'register was successful',
            }
        return Response(res)
    
    # User login
    @action(detail=False, methods=['post'])
    def login(self,request):
        data = json.loads(request.body)
        print(data)
        filter_user = User.objects.filter(username=data['username'])
        if not len(filter_user):
            res = {
                'success':False,
                'mess':'user does not exist'
            }
            return Response(res)
        user = UserSerializer(filter_user,many=True).data[0]
        check_pass_result = check_password(data['password'],user['password'])
        if not check_pass_result:
            res = {
                'success':False,
                'mess':'Password error'
            }
            return Response(res)
        
        res = {
                'success':True,
                'mess':'Login successful'
        }
        response = Response(res)
        response['Access-Control-Expose-Headers'] = 'auth'
        response['auth'] = create_token(user)
        return response

    # View all users
    @action(detail=False, methods=['get'])
    def all_users(self,request):
        # Login verification with token
        try:
            token = request.META.get('HTTP_AUTH')
            token = verify_token(token)
            if not token:
                res = {
                    'success':False,
                    'mess':'Please login again'
                }
                return Response(res)
            users = UserSerializer(User.objects.all(),many=True).data
            res = {
                'success':True,
                'data':users
            }
            response = Response(res)
            response['Access-Control-Expose-Headers'] = 'auth'
            response['auth'] = token
            return response
        except:
            res = {
                'success':False,
                'mess':'Login!'    
            }
            return Response(res)

    # log out
    @action(detail=False, methods=['post'])
    def logout(self,request):
        # Login verification with token
        username = 'guest'
        try:
            token = request.META.get('HTTP_AUTH')
            token = verify_token(token)
            # print('{}要退出登录'.format(username))
            if not token:
                res = {
                    'success':True,
                    'mess':'Not logged in'
                }
                return Response(res)

            username = tokenUserInfo(token)
        
            res = {
                    'success':True,
                    'message':'{} log out'.format(username),
                }
            print('{}log out'.format(username))
            response = Response(res)
            return response
        except:
            res = {
                    'success':True,
                    'message':"Login!"
            }
            return Response(res)

    # Get user login user name
    @action(detail=False, methods=['get'])
    def getUserState(self,request):
        # token
        try:
            token = request.META.get('HTTP_AUTH')
            token = verify_token(token)
            if not token:
                res = {
                    'success':False,
                    'username':"guest",
                    'message':"请登录!"
                }
                return Response(res)

            print("当前登录的用户是:"+tokenUserInfo(token))
            
            res = {
                'success':True,
                'username':tokenUserInfo(token),
                'message':"登录校验成功!"
            }
            response = Response(res)
            response['Access-Control-Expose-Headers'] = 'auth'
            response['auth'] = token
            return response
        except:
            res = {
                    'success':False,
                    'username':"guest",
                    'message':"请登录!"
            }
            return Response(res)



