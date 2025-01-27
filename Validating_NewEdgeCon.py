import numpy as np
import random
import time
import math
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from models import DQN
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from sklearn import preprocessing
from collections import namedtuple

num_node = 30
file = open("Data\data_" + str(num_node) + ".txt", 'r', encoding='UTF-8') 
line = file.readlines()

num_node = int(line[0])
num_edge = int(line[1])
num_agent = int(line[num_node + num_edge + 2])
constraint = int(line[num_node + num_edge + num_agent + 3])
maxspeed = 0 
Cost = 0
lists = "Model\_3f_NewEdgeCon"
# lists = "Model\_3f_NewEdgeCon_2"
# lists = "Model\saved_"

class Node:
    def __init__(self, pos, number):
        self.pos = pos
        self.number = number
        self.connected_node = []        
        self.in_commu_range = []        #溝通範圍(constraint)內的node
        self.all_ag_here = []           #在這個node上的agent
        
class Edge:
    def __init__(self, distance, number):
        self.ox = 'x'
        self.distance = distance        
        self.number = number
        self.count = 0
        
class Agent:
    def __init__(self, cur, speed, number):
        self.currnode_ori = cur
        self.currnode = cur         
        self.togonode = cur         
        self.lastedge = 0
        self.togoedge = 0
        self.curedge_length = 0     
        self.step = 0
        self.speed = speed
        self.cost = 0
        self.num = number
        self.historyaction = []
        self.reward = 0
        self.start = cur
        self.edgeLengthInfo = []
        self.edgeTotalConnectMap = []
        self.edgeTotalConnectInfo = []
        self.edgeCountInfo = []
        self.featureUpdate = []
        for i in range(num_edge):   
            self.edgeLengthInfo.append(0)
            self.edgeCountInfo.append(0)
        for i in range(num_node):   
            j = set()
            self.edgeTotalConnectMap.append(j)
            self.edgeTotalConnectInfo.append(0)
        for i in range(num_agent): 
            j = set()
            self.featureUpdate.append(j)

node_ALL = []
edge_ALL = {}
agent_ALL = []

for i in range(num_node):
    k = i + 2
    line[k] = line[k].split()
    for j in range(len(line[k])): 
        line[k][j] = int(line[k][j])
    l = Node((line[k][1], line[k][2]), line[k][0])
    node_ALL.append(l)

for i in range(num_edge):
    k = num_node + i + 2
    line[k] = line[k].split()
    for j in range(len(line[k])): 
        line[k][j] = int(line[k][j])
    l = Edge(line[k][2], i)
    line[k].pop()
    edge_ALL[tuple(line[k])] = l 
    start = line[k][0]
    end = line[k][1]
    node_ALL[start].connected_node.append(end)   
    node_ALL[end].connected_node.append(start)

for i in range(num_agent):
    k = num_node + num_edge + i + 3
    line[k] = line[k].split()
    for j in range(len(line[k])): 
        line[k][j] = int(line[k][j])
    l = Agent(int(line[k][1]), int(line[k][2]), int(line[k][0]))
    agent_ALL.append(l)
    if(maxspeed < int(line[k][2])): maxspeed = int(line[k][2])
    node_ALL[l.currnode].all_ag_here.append(i)

#算哪些node在溝通範圍(constraint)內
def cal_dis(a,b):    return np.sqrt(np.square(abs(a.pos[0]-b.pos[0]))+np.square(abs(a.pos[1]-b.pos[1])))
for i in range(num_node):
    for j in range(num_node):
        if(cal_dis(node_ALL[i],node_ALL[j]) <= constraint): node_ALL[i].in_commu_range.append(j)

def find_edge(a,b):
    if tuple([a,b]) in edge_ALL:   return tuple([a,b])
    else: return tuple([b,a])

# 特徵矩陣 (todo)
num_feature = 3
def feature_matrix(ag):
    X = np.zeros((num_node, num_feature))
    for k in node_ALL[ag.currnode].connected_node:
        ed = edge_ALL[find_edge(ag.currnode,k)].number
        # 距離
        if ag.edgeLengthInfo[ed] != 0:            
            X[k][0] = ag.edgeLengthInfo[ed]
        # 被幾個edge走到
        if ag.edgeTotalConnectInfo[k] != 0: X[k][1] = (ag.edgeTotalConnectInfo[k] - len(ag.edgeTotalConnectMap[k]))/(num_node-1)*10
        else: X[k][1] = 10
        # 此edge被走過幾次
        X[k][2] = ag.edgeCountInfo[ed]
    X = np.around((X), decimals=3)
    return X

def update_info():
    for u in range(num_agent):
        for give in agent_ALL:
            for receive in agent_ALL:
                if receive.currnode in node_ALL[give.currnode].in_commu_range and give.num != receive.num:
                    j = set()
                    for infomation in set(give.featureUpdate[receive.num]):
                        feat, edge = infomation
                        if feat == 0:  
                            if receive.edgeLengthInfo[edge] == 0:
                                receive.edgeLengthInfo[edge] = give.edgeLengthInfo[edge]
                                j.add(infomation)
                        if feat == 11: 
                            if len(receive.edgeTotalConnectMap[edge]) < num_node-1:
                                receive.edgeTotalConnectMap[edge] = receive.edgeTotalConnectMap[edge].union(give.edgeTotalConnectMap[edge])
                                j.add(infomation)
                        if feat == 12:  
                            if receive.edgeTotalConnectInfo[edge] < give.edgeTotalConnectInfo[edge]: 
                                receive.edgeTotalConnectInfo[edge] = give.edgeTotalConnectInfo[edge]
                                j.add(infomation)
                        if feat == 2:  
                            if receive.edgeCountInfo[edge] < give.edgeCountInfo[edge]: 
                                receive.edgeCountInfo[edge] = give.edgeCountInfo[edge]
                                j.add(infomation)
                    for i in range(num_agent): 
                        if i != give.num and i != receive.num: receive.featureUpdate[i] = receive.featureUpdate[i].union(j)
                    give.featureUpdate[receive.num].clear()
                elif give.num == receive.num: give.featureUpdate[receive.num].clear()

model = DQN(nfeat=num_feature)
model.load_state_dict(torch.load(lists))

def pick_edge(ag):    
    X = feature_matrix(ag)
    output = model(torch.from_numpy(X))
    outputnum = -1
    outputmax = -math.inf
    for i in range(num_node):
        if output[i] >= outputmax and i in node_ALL[ag.togonode].connected_node:
            outputmax = output[i]
            outputnum = i
    return outputnum

def walking(ag):
    if ag.currnode_ori != ag.togonode : 
        #edge lengh feature
        edge_ALL[find_edge(ag.currnode_ori, ag.togonode)].ox = 'o'
        ag.edgeLengthInfo[edge_ALL[ag.togoedge].number] = ag.curedge_length
        for i in range(num_agent): ag.featureUpdate[i].add(tuple([0, edge_ALL[ag.togoedge].number]))
       
    ag.currnode = ag.togonode
    ag.currnode_ori = ag.togonode
    ag.lastedge = ag.togoedge
    ag.historyaction.append(ag.togonode)
    ag.step = ag.step - ag.curedge_length  
    ag.togonode = pick_edge(ag)
    togo_edge = find_edge(ag.currnode, ag.togonode)
    ag.curedge_length = edge_ALL[togo_edge].distance
    ag.togoedge = togo_edge
    
     #edge count feature
    edge_ALL[ag.togoedge].count += 1
    ag.edgeCountInfo[edge_ALL[ag.togoedge].number] = edge_ALL[ag.togoedge].count
    for i in range(num_agent): ag.featureUpdate[i].add(tuple([2, edge_ALL[ag.togoedge].number]))
    #edge connect feature
    ag.edgeTotalConnectMap[ag.currnode_ori].update({ag.togonode})
    ag.edgeTotalConnectMap[ag.togonode].update({ag.currnode_ori})
    for i in range(num_agent): ag.featureUpdate[i].add(tuple([11, ag.currnode_ori]))
    for i in range(num_agent): ag.featureUpdate[i].add(tuple([11, ag.togonode]))
    ag.edgeTotalConnectInfo[ag.currnode] = len(node_ALL[ag.currnode].connected_node)
    for i in range(num_agent): ag.featureUpdate[i].add(tuple([12, ag.currnode]))


k = 10000
while not all(edge_ALL[r].ox == 'o' for r in edge_ALL):
    for ag in agent_ALL:
        ag.step += ag.speed
        ag.cost += ag.speed
        while ag.curedge_length <= ag.step:  
            update_info()
            node_ALL[ag.currnode].all_ag_here.remove(ag.num)
            walking(ag)         
            node_ALL[ag.currnode].all_ag_here.append(ag.num)
        if ag.step > ag.curedge_length/2:
            node_ALL[ag.currnode].all_ag_here.remove(ag.num)       
            ag.currnode = ag.togonode
            node_ALL[ag.currnode].all_ag_here.append(ag.num)
            update_info()
    Cost += maxspeed
    if Cost > k:
        print(Cost)
        k += 10000

# Write all action to file
fileforHistoryaction = "Animation/RL_newedgecon_"+ str(num_node) +".txt"
f = open(fileforHistoryaction, "w")
print(num_node, file = f)
for i in agent_ALL: print(i.historyaction, file = f)

allEdgeCost = 0
for i in edge_ALL:   allEdgeCost += edge_ALL[i].distance
allAgentCost = 0
for i in agent_ALL:   allAgentCost += i.cost
all_historyaction = -num_agent
for i in agent_ALL:  all_historyaction += len(i.historyaction)

# for i in agent_ALL:   print(i.historyaction)
print("Map cost = ",allEdgeCost)
print("All agents' cost = ",allAgentCost)
print("Repeated rate = ","%.2f"%((all_historyaction-num_edge)/all_historyaction*100),"%")                      
print("Largest cost = ",Cost)