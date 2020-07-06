# 解析元数据中 数据有关信息
# 导入库
import os
from .utils import  datasRoot,datasetMap,transMap,commonRoot,userDRoot,CommonDataSetCollections,userDSpace
from .transforms import transforms as T
# import transforms.transforms as T
from .Reader import  TLImageClassificationReader
import numpy as np
# 解析数据操作算子
def  parseTrans(meta_trans):
    """
         trans-meta : 数据变换元数据
         两大类:
            1. name + paramters 调用方式, paramters个数不同;
            2. lambda式调用, "lambda" + "str-xxxx"
    """
    if meta_trans is None:
        raise ValueError("Transforms Can not be None")
    # 数据操作 列表
    operas_list = []
    for operaItem in meta_trans:
        opera_name = None
        opera_paramters = []
        for index,parName in enumerate( operaItem.keys() ):
            if parName == 'name':
                opera_name = operaItem[ parName ] 
            else:
                opera_paramters.append(operaItem[parName])
        
        if opera_name not in transMap:
            raise NotImplementedError("NotSupported {} Operation".format(opera_name))

        if opera_name == "Lambda":
            lambdaFuncUserDefine = None
            try:
                lambdaFuncUserDefine = eval(opera_paramters[0])
            except BaseException:
                raise NotImplementedError("Lambda Operation Compiler Error")
            finally:
                lambdaFuncUserDefine = eval('lambda x : x')
            operas_list.append(transMap[ opera_name ](lambdaFuncUserDefine))
        else:
            if len(opera_paramters) == 0:
                operas_list.append( transMap[opera_name]() )
            elif len(opera_paramters) == 1:
                operas_list.append( transMap[ opera_name ]( opera_paramters[0] ) )
            elif len(opera_paramters) == 2:
                operas_list.append( transMap[ opera_name ]( opera_paramters[0] , opera_paramters[1] ) )


    transforms = T.Compose(operas_list)
    return transforms

# 解析数据集信息
def parseDataSet(author,meta_dataset,transforms):
    if meta_dataset is None:
        raise ValueError("DataSet Can Not Be Set None")
    dataset = None
    # 列出当前用户支持的数据集
    userDsCollections = os.listdir(userDSpace.format(author))

    # 用户个人数据集 + 系统内置的数据集
    dataSetSupported = userDsCollections + CommonDataSetCollections

    dataset_name = meta_dataset['name']

    if dataset_name not in dataSetSupported:
        raise NotImplementedError("NotSupported {} DataSet".format(dataset_name))
    
    if dataset_name in CommonDataSetCollections:
        # 系统内置类
        dataset = datasetMap[ dataset_name ]( commonRoot , transform= transforms)
    else:
        # 用户个人数据集
        dataset = datasetMap[ "ImageFolder" ]( userDRoot.format(author,dataset_name) , transform= transforms)
    #数据切分比例
    dsSpiltRatios = [meta_dataset['train'],meta_dataset['dev'],meta_dataset['test']]

    dataloader = TLImageClassificationReader(dataset,dsSpiltRatios)
    
    return dataset,dataloader
