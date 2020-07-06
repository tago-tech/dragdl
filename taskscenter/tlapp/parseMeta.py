
def keyParamters(node):
    """
        过滤得到关键参数
    """

    filterParmeters = ['type','shapeUI','id']
    if node is None:
        return None
    else:
        keyParamterDict = {}
        for key in node['shape'].keys():
            if key not in filterParmeters:
                keyParamterDict[key] = node['shape'][key]
        return keyParamterDict

def  parseMeta(meta):
    """
        meta: json型 配置信息,包括 nodes 和 edges 两大类;
        nodes 中 节点的 详细信息,edges 中节点之间的连边;
    """
    
    edges = meta['edges']
    nodes = meta['nodes']

    nodeToIdx,idxToNode = {},{}
    
    nodeModel,nodeDataSet,nodesTrans = None,None,[]
    
    for node in nodes:
        nodeType,nodeIdx = node['shape']['type'],node['id']
        # nodeToIdx[str(node)] = nodeIdx
        idxToNode[nodeIdx] = node
        if nodeType == 'DataSet':
            nodeDataSet = node
        elif nodeType == 'MODEL':
            nodeModel = node
        else:
            nodesTrans.append(node)

    transChain = []
    #分析Transform的顺序,构造链表
    count,index = len(nodesTrans)-1,0
    while index < len(edges):
        sourceidx,targetidx = edges[index]['source'],edges[index]['target']
        sourceTye,targetTye = idxToNode[sourceidx]['shape']['type'],idxToNode[targetidx]['shape']['type']
        if sourceTye == 'TransForm' and targetTye == 'MODEL' and sourceidx not in transChain:
            
            transChain.append(sourceidx)
            index = 0
            continue

        if sourceTye == 'TransForm' and targetTye == 'TransForm' and len(transChain) > 0 and targetidx == transChain[-1] and sourceidx not in transChain:
            transChain.append(sourceidx)
            index = 0
            continue
        index += 1
    
    transChain.reverse()
    nodesTrans =sorted(nodesTrans,key=lambda item:transChain.index(item['id']))    
    nodesTrans = [keyParamters(nodeTran) for nodeTran in nodesTrans]
    nodeModel,nodeDataSet = keyParamters(nodeModel),keyParamters(nodeDataSet)
    return nodeModel,nodeDataSet,nodesTrans