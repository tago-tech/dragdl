## tlapp

## 目录组织:

    tlib - 负责预训练模型配置,元数据中 模型参数解析;
    dlib - 负责数据集以及数据预处理代码实现,以及元数据中数据部分参数解析;
    functools - 负责一些辅助函数;
    models - 存储生成的模型;
    test.py - 负责单机测试; 
    tasks.py - 负责 分布式异步 测试;
    dfgExample.json - 数据流图样例Json文件,供测使用;



## tips:

    训练日志样例
    
    训练集
    [2020-01-02 06:02:57,286: INFO/ForkPoolWorker-7] taskscenter.tasks.mockTask[70e921f6-af61-4ae2-964f-29442af80ded]: step 62: loss=2.24649 acc=0.00000 [step/sec: 0.24]

    验证集
    [2020-01-02 06:03:45,647: INFO/ForkPoolWorker-7] taskscenter.tasks.mockTask[70e921f6-af61-4ae2-964f-29442af80ded]: [dev dataset evaluation result] loss=2.44263 acc=0.00000 [step/sec: 0.70]

    测试集
    [2020-01-02 06:04:14,691: INFO/ForkPoolWorker-7] taskscenter.tasks.mockTask[70e921f6-af61-4ae2-964f-29442af80ded]: [test dataset evaluation result] loss=2.23493 acc=0.15000 [step/sec: 0.70]
