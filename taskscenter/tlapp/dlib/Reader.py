"""
    定义loader

"""
# 导入库
import os
import paddle
from PIL import Image
import numpy as np



class TLImageClassificationReader(object):

    def __init__(self,dataset,spiltRatios=[7,1,2]):
        """
            初始化各种参数
            dataset: 需要 迭代的数据集
        """
        self.dataset = dataset
        
        self.totalSize = len(dataset)

        #切分 train : dev : test = 7 : 1 : 2 
        if len(spiltRatios) != 3 or sum(spiltRatios) != 10:
            raise ValueError("DataSet Spilt(train : dev : test = x : y : z,x + y + z = 10)")
            
        self.split_poses = [spiltRatios[0] * 0.1,1.0 - spiltRatios[-1] * 0.1]
        self.datas_indices = [ index for index in range(self.totalSize)]
        self.train_examples,self.dev_examples,self.test_examples = self.data_split(self.totalSize,self.split_poses)

    def data_split(self,totalSize,split_poses):

        np.random.shuffle(self.datas_indices)
        train_examples =  self.datas_indices[ :int(totalSize * split_poses[0]) ]
        dev_examples =  self.datas_indices[ int(totalSize * split_poses[0]) : int( totalSize * split_poses[1]) ]
        test_examples = self.datas_indices[int(totalSize * split_poses[1]) : ]
        return train_examples,dev_examples,test_examples


    def data_generator(self,batch_size,phase='train',shuffle=False,data=None):
        """
            数据生成器
        """
        if phase == "train":
            data = self.train_examples
        elif phase == "test":
            shuffle = False
            data = self.test_examples
        elif phase == "val" or phase == "dev":
            shuffle = False
            data = self.dev_examples
        elif phase == "predict":
            data = data
        # 预测时数据处理
        def preprocess(image_path):

            sampler = None
            with open(image_path, 'rb') as f:
                sampler = Image.open(f)
                sampler = sampler.convert('RGB')

            transfrom = self.dataset.transform

            if transfrom is not None:
                sampler = transfrom(sampler)
            return sampler

        def data_reader():
            if phase == "predict":
                for image_path in data:
                    imgND = preprocess(image_path)
                    imgND = np.array(imgND)
                    yield (imgND,)
            else:
                for index in data:
                    imgND,labelND = self.dataset[index][0],self.dataset[index][1] 
                    imgND ,labelND = np.array(imgND),np.array(labelND)
                    yield (imgND,labelND)
        return paddle.batch(data_reader,batch_size=batch_size)
        # return paddle.batch(data_reader,batch_size=batch_size,drop_last=True)


    def get_train_examples(self):
        #return self.dataset.train_examples
        return self.train_examples

    def get_dev_examples(self):
        #return self.dataset.dev_examples
        return self.dev_examples

    def get_test_examples(self):
        return self.test_examples