from rest_framework import serializers
from taskscenter.models import Task

# 序列化对象
class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ('task_name','task_author','task_type','task_note','task_state','build_time','last_timestamp')