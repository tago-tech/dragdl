from rest_framework import serializers
from userapp.models import User

# 序列化对象
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('username','password')