# 单机测试脚本
import logging
from start import parse_and_train

logging.getLogger().setLevel(logging.INFO)
logging.basicConfig(level = logging.INFO,format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

meta = None 
with open('example.json','r') as f:
    meta = json.load(f)
parse_and_train(meta,logger)