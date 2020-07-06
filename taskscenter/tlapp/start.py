#Mutil-workers Script
import os
import json 
import numpy as np
import paddlehub as hub
from .parseMeta import parseMeta
from .dlib.parse_for_data import parseDataSet,parseTrans
from .tlib.parse_for_modle import parseModelConfig
from .tlib.tltask import ImageClassifierTask
#训练过程
def  train(task,logger):
    logger.info("Train Process Start")
    task.finetune_and_eval()

# 解析元信息并训练
def  parse_and_train(meta,logger):

    # 解析用户信息
    author = meta['username']
    # 解析工程名称
    appname = meta['taskname']
    # meta 还原
    meta = meta[ 'meta' ]
    
    modelMeta,dataSetMeta,transformsMeta = parseMeta(meta)

    #解析数据处理流
    transforms = parseTrans(transformsMeta) 

    #解析数据集
    dataset , data_loder = parseDataSet(author,dataSetMeta,transforms)
    
    logger.info("[DataSet:{};\nTransForm:{}\n[train : dev : test = {} : {} : {}]\n]".format(
                dataset,
                dataset.transform,
                len(data_loder.train_examples),
                len(data_loder.dev_examples),
                len(data_loder.test_examples)
                ))
    
    #解析训练配置、预训练模型
    config , module , feature_trainable = parseModelConfig(author,appname,modelMeta)

    #创建训练任务
    input_dict, output_dict, program = module.context(trainable=feature_trainable)
    img = input_dict["image"]
    feature_map = output_dict["feature_map"]
    feed_list = [img.name]

    task = ImageClassifierTask(
                data_reader=data_loder,
                feed_list=feed_list,
                feature=feature_map,
                num_classes=dataSetMeta['num_class'],
                config=config,
                logger=logger)
    #启动训练
    train(task,logger)
    

# 预测过程
def  predict(data,task,logger):
    logger.info("Inference")
    results = task.predict(data)
    return results

# 解析元信息并预测
def parse_and_predict(data,path2Meta,logger):
    
    if not os.access(path2Meta,os.R_OK):
        raise IOError("No App Existed")
    meta = None
    with open(path2Meta,'r') as f:
        meta = json.load(f)

    # 解析用户信息
    author = meta['username']
    # 解析工程名称
    appname = meta['taskname']
    # meta 还原
    meta = meta[ 'meta' ]
    
    modelMeta,dataSetMeta,transformsMeta = parseMeta(meta)

    transforms = parseTrans(transformsMeta) 

    dataset , data_loder = parseDataSet(author,dataSetMeta,transforms)
    
    config , module , feature_trainable = parseModelConfig(author,appname,modelMeta)
    
    input_dict, output_dict, program = module.context(trainable=True)
    img = input_dict["image"]
    feature_map = output_dict["feature_map"]
    feed_list = [img.name]

    task = ImageClassifierTask(
                data_reader=data_loder,
                feed_list=feed_list,
                feature=feature_map,
                num_classes=dataSetMeta['num_class'],
                config=config,
                logger=logger)

    index = 0
    run_states = task.predict(data=data)

    results = [run_state.run_results for run_state in run_states]
    
    res = {
        'result':'',
        'socres':[],
        'classes':[]
    }
    socres = []

    for batch_result in results:
        socres = batch_result[0][0]
        batch_result = np.argmax(batch_result, axis=2)[0]
        for result in batch_result:
            index += 1
            logger.info("input %i , and the predict result is %s" %
              (index, dataset.classes[result]))
            res['result'] = str(dataset.classes[result])+ '#' +str(result)
    res['socres'] = [str(digital) for digital in socres]
    res['classes'] = list(dataset.classes)
    return res