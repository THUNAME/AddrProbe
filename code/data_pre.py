import os
import csv, sys
import pandas as pd
from collections import Counter
import pyasn
import numpy as np

from config import DefaultConfig

config = DefaultConfig()


def read_file(filename):
    ip_list = []
    with open(filename, 'r') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            ip = row[0]
            ip_list.append(ip)
    return ip_list


def tran_ipv6(sim_ip):
    if sim_ip == "::":
        return "0000:0000:0000:0000:0000:0000:0000:0000"
    ip_list = ["0000", "0000", "0000", "0000", "0000", "0000", "0000", "0000"]
    if sim_ip.startswith("::"):
        temp_list = sim_ip.split(":")
        for i in range(0, len(temp_list)):
            ip_list[i + 8 - len(temp_list)] = ("0000" + temp_list[i])[-4:]
    elif sim_ip.endswith("::"):
        temp_list = sim_ip.split(":")
        for i in range(0, len(temp_list)):
            ip_list[i] = ("0000" + temp_list[i])[-4:]
    elif "::" not in sim_ip:
        temp_list = sim_ip.split(":")
        for i in range(0, len(temp_list)):
            ip_list[i] = ("0000" + temp_list[i])[-4:]
    # elif sim_ip.index("::") > 0:
    else:
        temp_list = sim_ip.split("::")
        temp_list0 = temp_list[0].split(":")
        # print(temp_list0)
        for i in range(0, len(temp_list0)):
            ip_list[i] = ("0000" + temp_list0[i])[-4:]
        temp_list1 = temp_list[1].split(":")
        # print(temp_list1)
        for i in range(0, len(temp_list1)):
            ip_list[i + 8 - len(temp_list1)] = ("0000" + temp_list1[i])[-4:]
    return ":".join(ip_list)


# 除知识库外
def get_other_prefix_attr(df_seed_prefix, df_all_as_attr):

    df_all_prefix = pd.read_csv(config.ipasn_path, skiprows = 6, sep = "\t")
    df_all_prefix.columns = ['prefix', 'as']
    df_seed_prefix.columns = ['prefix', 'seed_num']


    df_few_seed_prefix = df_seed_prefix[0 < df_seed_prefix['seed_num']]
    df_few_seed_prefix = df_few_seed_prefix[df_few_seed_prefix['seed_num'] < config.knowledge_base_threshold]
    df_few_seed_prefix = pd.merge(df_few_seed_prefix, df_all_prefix)
    df_few_seed_prefix = df_few_seed_prefix.drop(['seed_num'], axis=1)  
    df_seed_prefix = df_seed_prefix.drop(['seed_num'], axis=1)  
    df1 = pd.merge(df_all_prefix, df_seed_prefix, on = ['prefix'])
    df_no_seed_prefix = pd.concat([df_all_prefix, df1], axis = 0).drop_duplicates(keep=False)
    df_no_seed_prefix = df_no_seed_prefix.reset_index(drop=True)


    df_other = pd.concat([df_no_seed_prefix, df_few_seed_prefix], axis = 0)
    df_other = df_other.drop_duplicates(keep='last')
    df_other["id"] = range(df_other.shape[0])

    df_other_as_attr = pd.merge(df_other,df_all_as_attr,on = ['as'], how='left')
    df_other_as_attr = df_other_as_attr[['id', 'prefix', 'as', 'org_name']]
    df_other_as_attr.to_csv(config.other_prefix_attr_path, index = False)


def data_pre(filename):
    ip_list = []
    list_a = read_file(filename)
    for i, val in enumerate(list_a):
        ip_list.append(tran_ipv6(val))

    ip_df = pd.DataFrame(ip_list, columns=['address'])

    # remove_duplicate_addresses
    ip_df.drop_duplicates(subset=ip_df.columns, keep='last', inplace=True)
    print("*" * 20 + "number of seed addresses: ", ip_df.shape)
    ip_df["prefix_pyasn"] = None


    asndb = pyasn.pyasn(config.ipasn_path)

    for index, row in ip_df.iterrows():
        prefix_pyasn = asndb.lookup(row['address'])[1]
        row["prefix_pyasn"] = prefix_pyasn
    ip_df_group = ip_df.groupby('prefix_pyasn')

    # suitable prefix
    ip_prefix_list = ip_df["prefix_pyasn"].to_list()
    result = Counter(ip_prefix_list)
    result_list = []
    seed_num = []
    for k, v in result.items():
        if k != None:
            seed_num.append([k, v])
            if v >= config.knowledge_base_threshold:
                result_list.append(k)
    df_seed_num = pd.DataFrame(seed_num, columns=['prefix_index', 'seed_num'])
    df_seed_num.sort_values(by=['seed_num'],inplace=True)
    path = config.model_prefix_seed_number
    df_seed_num.to_csv(path, sep=':', header=False, index=False)

    list_id_as = []
    for prefix_id in range(len(result_list)):
        prefix_group = ip_df_group.get_group(result_list[prefix_id])
        print(f"prefix_id: {prefix_id}",  'seed num: ',prefix_group.shape[0])
        
        # get AS number
        prefix_as = asndb.lookup(result_list[prefix_id][0:-3])[0]
        list_id_as.append([prefix_id, result_list[prefix_id], prefix_as, prefix_group.shape[0]])

        prefix_group = prefix_group["address"].str.replace(':', '').astype(str).to_frame()

        list_all = []
        for index, row in prefix_group.iterrows():
            list_temp = list(row["address"])
            list_all.append(list_temp)
        df_entropy = pd.DataFrame(data=list_all)

        list_all = []
        for index, row in df_entropy.iterrows():
            list_temp = row.to_list()
            for j in range(32):
                if list_temp[j] in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']:
                    continue
                elif list_temp[j] == 'a':
                    list_temp[j] = '10'
                elif list_temp[j] == 'b':
                    list_temp[j] = '11'
                elif list_temp[j] == 'c':
                    list_temp[j] = '12'
                elif list_temp[j] == 'd':
                    list_temp[j] = '13'
                elif list_temp[j] == 'e':
                    list_temp[j] = '14'
                elif list_temp[j] == 'f':
                    list_temp[j] = '15'
            list_all.append(list_temp)

        prefix_group = pd.DataFrame(data=list_all)
        path = config.data_path + '{prefix_id}.txt'.format(prefix_id=prefix_id)
        prefix_group.to_csv(path, sep=',', header=False, index=False)

    # All AS properties
    df_all_as_attr = pd.read_csv('../data/input/all_as_attr.csv',low_memory=False)[['as','org_name']]

    df_id_prefix_as = pd.DataFrame(data = list_id_as, columns = ['id','prefix','as', 'seednum'])
    df_id_prefix_as_attr = pd.merge(df_id_prefix_as,df_all_as_attr,on = ['as'], how='left')
    df_id_prefix_as_attr.to_csv(config.model_prefix_attr_path, index = False)
    get_other_prefix_attr(df_seed_num, df_all_as_attr)





if __name__ == "__main__":
    folder = '../data/input/seeds_dataset.txt'  
    data_pre(folder)
