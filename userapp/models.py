from django.db import models

# Create your models here.
class User(models.Model):
    # 用户名
    username = models.CharField(max_length=10,unique=True)
    # 用户密码
    password = models.CharField(max_length=20)

