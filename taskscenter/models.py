from django.db import models
# from userapp.models import User
# Create your models here.
class Task(models.Model):
    # 任务状态类型Choices(待运行\运行中\成功\失败)
    taskStatus = (
        ('TASK_WAITING','TASK_WAITING'),
        ('TASK_RUNNING','TASK_RUNNING'),
        ('TASK_SUCCESSFUL','TASK_SUCCESSFUL'),
        ('TASK_FAILED','TASK_FAILED')
    ) 
    # 任务类型Choices(tl,nas)
    taskTypes = (
        ('TL.A','TL.A'),
        ('NAS.A','NAS.A'),
        ('TL.B','TL.B'),
        ('NAS.B','NAS.B')
    )

    # Django Model 默认 int型 主键 [ id ]  自增

    # 任务名
    task_name = models.CharField(max_length=20,null=False)
    # 用户名(外键,设置默认值root)
    task_author = models.ForeignKey(to='userapp.User',on_delete=models.CASCADE)
    # 任务类型(Choise,设置默认值)
    task_type = models.CharField(max_length=20,choices=taskTypes,default='TL.A')
    # 任务 训练用 Meta 路径,taskmetapath(not null)
    task_meta = models.CharField(max_length=100)
    # 任务备注,tasknote,textfiled(not null) 
    task_note = models.CharField(max_length=200,null=False,blank=False)
    # 任务状态(Chiose,设置默认值)
    task_state = models.CharField(max_length=20,choices=taskStatus,default='TASK_WAITING')
    #  任务创建时间DataFiled(not null)
    build_time = models.DateTimeField(auto_now_add=True)
    # 任务异步 task-id (null = True)
    async_task_id = models.CharField(max_length=100,null=True)
    # 任务模型路径taskModelPath(null=True)
    async_model_path = models.CharField(max_length=100,null=True) 
    # 任务日志路径taskLogPath(null=True)
    async_log_path = models.CharField(max_length=100,null=True)
    #  任务预测所用meta路径(null=True)
    predict_meta = models.CharField(max_length=100,null=True)
    #  任务最后修改时间 lastEditTimeStamp(null=True)
    last_timestamp = models.DateTimeField(auto_now=True)