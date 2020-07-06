

root = './taskscenter/tlapp/'
# 模型存储位置
moduleRoot = root + "tlib/hub/modules/"

# 模型对应表
moduleMap = {
    "resnet50": "resnet_v2_50_imagenet",
    "resnet101": "resnet_v2_101_imagenet",
    "resnet152": "resnet_v2_152_imagenet",
    "mobilenet": "mobilenet_v2_imagenet",
    "nasnet": "nasnet_imagenet",
    "pnasnet": "pnasnet_imagenet",
    "resnet_18":"resnet_v2_18_imagenet",
    "vgg16":"vgg16_imagenet"
}

#checkPoint root
checkPointRoot = root + "models/{}/{}/"