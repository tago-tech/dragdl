from django.contrib import admin
from taskscenter.models import Task
# Register your models here.
class TaskAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'task_name',
        'async_task_id',
        'task_author',
        'task_type',
        'task_meta',
        'task_note',
        'task_state',
        'build_time',
        'last_timestamp',
    ]
admin.site.register(Task,TaskAdmin)
