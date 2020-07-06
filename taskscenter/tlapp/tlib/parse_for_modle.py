# 从元数据中解析 预训练模型 和 训练配置
# 导入包
import os
import paddlehub as hub
from .utils import checkPointRoot,moduleMap,moduleRoot

def parseModelConfig( author,appname,meta_model ):

    # 分析 配置
    config = hub.RunConfig(
        use_cuda=False,
        num_epoch=meta_model['num_epoch'],
        checkpoint_dir=checkPointRoot.format(author,appname),
        batch_size=meta_model['batch_size'],
        log_interval=meta_model['log_interval'],
        eval_interval=meta_model['eval_interval'],
        strategy=hub.finetune.strategy.DefaultFinetuneStrategy())


    if meta_model['name'].lower() not in moduleMap:
        raise ModuleNotFoundError("NotSupport [{}] Model".format(meta_model['name'].lower()))
    #  分析 预训练 模型
    moudle_path = moduleRoot + moduleMap[meta_model['name'].lower()]

    # 直接取路径不太友好
    module = hub.Module(module_dir=[ moudle_path ])
    
    return config,module,meta_model['trainable']
