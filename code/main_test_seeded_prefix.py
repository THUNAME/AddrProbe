import os
import re, math, ast, copy
import subprocess
import torch
import pandas as pd
from cvae import CVAE
from evaluate import probe
from utils import *
from train import iter_train_specific_prefix
from config import DefaultConfig

config = DefaultConfig()
device = config.device

# init prob

def get_model_cluster_distribution():
    prefix_list = os.listdir(config.model_path)
    prefix_list = [int(re.sub(r"\.pth$", "", prefix)) for prefix in prefix_list]
    prefix_cluster_distribution_dict = dict()
    with open(config.init_cluster_info_path, 'r') as f:
        lines = f.readlines()
        # the prefix is the index of the line
        for prefix in prefix_list:
            cluster_distribution = lines[prefix].strip().split(",")
            prefix_cluster_distribution_dict[prefix] = [int(i) for i in cluster_distribution]
    return prefix_cluster_distribution_dict

def get_match_model_cluster_distribution(prefix, df_all_test_prefix, df_id_prefix_as_attr, prefix_cluster_distribution_dict, budget):
    test_prefix_attr =  df_all_test_prefix.iloc[prefix]
    test_prefix = test_prefix_attr['prefix']

    test_prefix_org = test_prefix_attr['org_name']
    # mathch_model_org = df_id_prefix_as_attr[df_id_prefix_as_attr['org_name'] == test_prefix_org][['id', 'prefix']].values.tolist()
    df_filter = df_id_prefix_as_attr[(df_id_prefix_as_attr['org_name'] == test_prefix_org) | (df_id_prefix_as_attr['prefix'] == test_prefix)][['id', 'prefix']].drop_duplicates()
    match_model_org = df_filter.values.tolist()
    
    sum_clu_dis = 0
    for model in mathch_model_org:
        cluster_distribution = prefix_cluster_distribution_dict[model[0]]
        model.append(cluster_distribution)
        sum_clu_dis = sum_clu_dis + sum(cluster_distribution)
    for model in mathch_model_org:
        model.append(round(sum(model[2])/sum_clu_dis * budget))
    return test_prefix, mathch_model_org

def prefix_conversion(test_prefix, generated_address_with_label):
    str_prefix, str_length = test_prefix.split('/')
    prefix_tran = format_str_to_standard(str_prefix)

    prefix_length = int(int(str_length) / 4)
    replace_length = int(math.ceil(prefix_length/4-1) + prefix_length)
    now_prefix = prefix_tran[:replace_length]
    print("now_prefix: ", now_prefix)

    for address in list(generated_address_with_label.keys()):
        new_address = now_prefix + address[replace_length:]
        generated_address_with_label[new_address] = generated_address_with_label.pop(address)

    return generated_address_with_label

def init_probe_specific_prefix(prefix, test_prefix, all_cluster_distribution, model_path, sum_alias_prefix):
    if sum_alias_prefix == None:
        sum_alias_prefix = []
    generated_address_with_label = dict()
    for cluster_distribution in all_cluster_distribution:
        model_id = cluster_distribution[0]
        budget = cluster_distribution[3]
        cluster_num = len(cluster_distribution[2])
        probe_loader = load_init_probe_label(cluster_distribution[2], budget)
        # load corresponding model
        model = CVAE(cluster_num).to(device)
        model.load_state_dict(torch.load(model_path + f"{model_id}.pth"))
        address_with_label = probe(model, probe_loader, model_id)
        generated_address_with_label.update(address_with_label)
    # print(generated_address_with_label)
    print('generated_address_with_label', len(generated_address_with_label))
    generated_address_with_label = prefix_conversion(test_prefix, generated_address_with_label)
    print('prefix_conversion generated_address_with_label', len(generated_address_with_label))

    # remove duplicate
    if config.is_model_prefix:
        remove_init_duplicate(prefix, generated_address_with_label)
    remove_bank_duplicate(prefix, generated_address_with_label)
    generated_address_num = len(generated_address_with_label)
    print('remove duplicate generated_address_num',generated_address_num)

    if generated_address_num > 0:
        # create config.address_bank_path/prefix.txt and write into it
        with open(config.address_bank_path + f"{prefix}.txt", 'a') as f:
            for address in generated_address_with_label.keys():
                f.write(address + "\n")
        # create config.generated_address_path/prefix.txt and write into it
        with open(config.generated_address_path + f"{prefix}.txt", 'w') as f:
            for address in generated_address_with_label.keys():
                f.write(address + "\n")

        generated_address_path = config.generated_address_path + '{prefix}'.format(prefix=prefix) + ".txt"
        zmap_result_path = config.zmap_result_path + '{prefix}'.format(prefix=prefix) + ".txt"
        print(f"Running zmap for prefix {prefix}...")
        cmd = (f"sudo -S zmap --ipv6-source-ip={config.local_ipv6} "
                f"--ipv6-target-file={generated_address_path} "
                f"-o {zmap_result_path} -M icmp6_echoscan -B 10M --verbosity=0")
        echo = subprocess.Popen(['echo',config.password], stdout=subprocess.PIPE,)
        p = subprocess.Popen(cmd, shell=True, stdin=echo.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        hit_rate = re.findall(r"\d+\.?\d*", p.communicate()[1][-10:].decode('utf-8'))[0]
        print(f"Hit rate: {hit_rate}%")

        # read zmap result and format from string to standard address
        zmap_active_address = []
        with open(zmap_result_path, 'r') as f:
            for line in f:
                zmap_active_address.append(format_str_to_standard(line.strip()))
        # merge zmap_active_address and generated_address_with_label
        # in this way, we can get the cluster label for each active address
        active_address_with_label = dict()
        for address in zmap_active_address:
            if address in generated_address_with_label:
                active_address_with_label[address] = generated_address_with_label[address]


        # generate df columns=['address', 'label']
        df_active_address_label = pd.DataFrame(active_address_with_label.items(), columns=['address', 'label'])
        if df_active_address_label.shape[0] != 0:
            temp_active_address_label = df_active_address_label['label'].apply(pd.Series,index=['model','label'])
            # print(temp_active_address_label)
            df_active_address_label = df_active_address_label.drop('label', axis = 1)
            df_active_address_label['model'] = temp_active_address_label['model']
            df_active_address_label['label'] = temp_active_address_label['label']
            active_address_num = df_active_address_label.shape[0]
        else:
            generated_address_num_after_del_alias = generated_address_num

        # remove alias prefix
        list_alias_prefix = []
        if df_active_address_label.shape[0] > 1:
            list_alias_prefix = alias_detection(df_active_address_label, prefix, test_prefix)
            # print('alias prefix :', list_alias_prefix)
            sum_alias_prefix = list(set(list_alias_prefix + sum_alias_prefix))
        
        if sum_alias_prefix and df_active_address_label.shape[0] != 0:
            for alias_prefix in sum_alias_prefix:
                df_active_address_label = df_active_address_label.loc[
                    df_active_address_label['address'].apply(
                        lambda s: re.search(alias_prefix, s) is None)].reset_index(
                    drop=True)
            print('active address after del alias:', df_active_address_label.shape[0])
            no_alias_active_address_num = df_active_address_label.shape[0]
            alias_active_address_num = active_address_num - no_alias_active_address_num
            generated_address_num_after_del_alias = generated_address_num - alias_active_address_num

        if df_active_address_label.shape[0] != 0:
            no_alias_active_address_num = df_active_address_label.shape[0]
            alias_active_address_num = active_address_num - no_alias_active_address_num
            generated_address_num_after_del_alias = generated_address_num - alias_active_address_num
            hit_rate_no_alias = round(no_alias_active_address_num/generated_address_num_after_del_alias * 100, 2)
            print('hit_rate_no_alias: ', hit_rate_no_alias)

            # save the active address with label into config.new_address_path/prefix.txt
            df_active_address_label.to_csv(config.new_address_path + f"{prefix}.txt",
                                            sep=',', header=False, index=False)
            # add the active address with label into config.new_address_path/all_prefix.txt
            with open(config.active_address_bank_path + f"all_{prefix}.txt", 'a') as f:
                for i in range(df_active_address_label.shape[0]):
                    f.write(df_active_address_label.iloc[i, 0] + "," + str(df_active_address_label.iloc[i, 1]) + "," + str(df_active_address_label.iloc[i, 2]) + "\n")

            # count the number of active address for each label in a list
            # temp_active_address_label = df_active_address_label['label'].apply(pd.Series,index=['model','label'])
            # df_active_address_label = df_active_address_label.drop('label', axis = 1)
            # df_active_address_label['model'] = temp_active_address_label['model']
            # df_active_address_label['label'] = temp_active_address_label['label']

            df_active_address_label_group = df_active_address_label.groupby('model')
            active_model = df_active_address_label['model'].unique().tolist()
            new_cluster_distribution = []
            for temp_list in all_cluster_distribution:
                if temp_list[0] in active_model:
                    model_group = df_active_address_label_group.get_group(temp_list[0]) 
                    series_count_label = model_group['label'].value_counts() 
                    temp_list[2] = [0] * len(temp_list[2])
                    for count_label in series_count_label.items():
                        temp_list[2][count_label[0]] = count_label[1]
                    new_cluster_distribution.append(temp_list[0:3])

            print(f"Active address number for each label: {new_cluster_distribution}")

            # new_cluster_distribution = ','.join(str(i) for i in new_cluster_distribution)
            # list_alias_prefix = ','.join(str(i) for i in list_alias_prefix)
            # os.remove(config.address_bank_path + f"{prefix}.txt")
            # os.remove(config.active_address_bank_path + f"all_{prefix}.txt")


            os.remove(zmap_result_path)
            os.remove(generated_address_path)
            return hit_rate, hit_rate_no_alias, list_alias_prefix, generated_address_num, generated_address_num_after_del_alias, new_cluster_distribution
        else:
            os.remove(zmap_result_path)
            os.remove(generated_address_path)
            hit_rate_no_alias = 0
            new_cluster_distribution = [[0]]
            return hit_rate, hit_rate_no_alias, list_alias_prefix, generated_address_num, generated_address_num_after_del_alias, new_cluster_distribution

    else:
        hit_rate = 0
        hit_rate_no_alias = 0
        list_alias_prefix = []
        new_cluster_distribution = [[0]]
        generated_address_num_after_del_alias = generated_address_num
        return hit_rate, hit_rate_no_alias, list_alias_prefix, generated_address_num, generated_address_num_after_del_alias, new_cluster_distribution

def init_probe_all_model():
    prefix_cluster_distribution_dict = get_model_cluster_distribution()
    prefix_hit_alias_list = []
    df_all_test_prefix = pd.read_csv(config.test_seeded_prefix_and_attr_path, sep = ',')
    df_id_prefix_as_attr = pd.read_csv(config.model_prefix_attr_path, sep = ',')
    model_path = config.model_path
    no_match = 0 

    path = config.zmap_result_path + 'prefix_hit_alias_info.txt'
    lines = ['prefix', 'test_prefix', 'hit_rate', 'hit_rate_no_alias', 'alias_prefix', 'num_init_probe_address', 'num_init_probe_address_after_del_alias', 'cluster_distribution']
    lines = ';'.join([str(i) for i in lines]) + '\n'
    with open(path, 'a') as f:
        f.write(lines)

    for prefix in range(df_all_test_prefix.shape[0]):
        print(f"---------start---------- init prob prefix for {prefix} ...")
        test_prefix, all_cluster_distribution  = get_match_model_cluster_distribution(prefix, \
                                df_all_test_prefix, df_id_prefix_as_attr, prefix_cluster_distribution_dict, config.init_prob_budget)
        # print(all_cluster_distribution)
        if all_cluster_distribution == []:
            no_match = no_match + 1
            continue

        hit_rate, hit_rate_no_alias, list_alias_prefix, generated_address_num, generated_address_num_after_del_alias, new_cluster_distribution = \
                            init_probe_specific_prefix(prefix, test_prefix, all_cluster_distribution, model_path, sum_alias_prefix = None)


        list_alias_prefix = ','.join(str(i) for i in list_alias_prefix)
        
        path = config.zmap_result_path + 'prefix_hit_alias_info.txt'
        lines = [prefix, test_prefix, hit_rate, hit_rate_no_alias, list_alias_prefix,generated_address_num, generated_address_num_after_del_alias, new_cluster_distribution]
        lines = ';'.join([str(i) for i in lines]) + '\n'
        with open(path, 'a') as f:
            f.write(lines)
    path = config.zmap_result_path + 'prefix_hit_alias_info.txt'
    df_prefix_hit_alias = pd.read_csv(path, delimiter=';')
    df_prefix_hit_alias = df_prefix_hit_alias.sort_values(by=['hit_rate_no_alias']).reset_index(drop=True)
    df_prefix_hit_alias.to_csv(path, index=False)


# iter prob

def get_init_prob_cluster_distribution():
    path = config.zmap_result_path + 'prefix_hit_alias_info.txt'
    df_prefix_hit_alias = pd.read_csv(path)
    # print(df_prefix_hit_alias)
    sum_hit_rate_no_alias = df_prefix_hit_alias['hit_rate_no_alias'].sum()
    sum_iter_budget = df_prefix_hit_alias.shape[0] * config.prefix_budget - df_prefix_hit_alias['num_init_probe_address'].sum()

    sum_gen_rate = (df_prefix_hit_alias['num_init_probe_address_after_del_alias']/config.init_prob_budget).sum()
    sum_hit_gen_rate = (df_prefix_hit_alias['hit_rate_no_alias']/sum_hit_rate_no_alias *  \
                                                df_prefix_hit_alias['num_init_probe_address_after_del_alias']/config.init_prob_budget/sum_gen_rate).sum()
    # Budget allocation takes into account both hit rate and gen rate
    df_prefix_hit_alias['iter_budget'] = (df_prefix_hit_alias['hit_rate_no_alias']/sum_hit_rate_no_alias *   \
                        df_prefix_hit_alias['num_init_probe_address_after_del_alias']/config.init_prob_budget/sum_gen_rate)/sum_hit_gen_rate * sum_iter_budget
    df_prefix_hit_alias['iter_budget'] = df_prefix_hit_alias['iter_budget'].astype(int)
    df_prefix_hit_alias = df_prefix_hit_alias.sort_values(by=['iter_budget']).reset_index(drop=True)
    path = config.zmap_result_path + 'test_prefix_hit_alias_budget_info.txt'
    df_prefix_hit_alias.to_csv(path, index=False)
    return df_prefix_hit_alias

def get_iter_train_data(prefix):
    df_data = pd.read_csv(config.new_address_path + f"{prefix}.txt", sep=',', header=None)
    df_data.columns=['address', 'model', 'label']
    df_data.drop_duplicates(subset = df_data.columns,keep='last',inplace=True)
    df_group_train_data = df_data.groupby('model')
    return df_group_train_data


def iter_probe_specific_prefix(prefix, test_prefix, budget, iter_info_record):
    print(f"---------start---------- iter prob prefix for {prefix} ...")
    # print(f"budget: {budget}")
    init_prob_record = iter_info_record[0]
    # print('init_prob_record: ', init_prob_record)
    hit_rate_no_alias = init_prob_record[3]
    if str(init_prob_record[4]) == "nan":
        init_prob_alias_prefix = []
    else:
        init_prob_alias_prefix = [i for i in init_prob_record[4].split(",")]
    init_prob_use_budget = int(init_prob_record[5])

    new_cluster_distribution = ast.literal_eval(init_prob_record[7])
    new_cluster_distribution = new_cluster_distribution

    realtime_budget =  budget

    if hit_rate_no_alias > 0.0:
        for temp_model_dis in new_cluster_distribution:
            # copy model to fining
            copy_model(temp_model_dis[0])
    i = 0
    sum_num_active = 0
    sum_generated_address_num = init_prob_use_budget
    sum_alias_prefix = init_prob_alias_prefix
    while hit_rate_no_alias > 0.0 and realtime_budget > 0:
        i = i + 1
        sum_model_num_active = 0
        print(f"**************** iter for {i} time, realtime_budget is {realtime_budget}")
        df_group_train_data = get_iter_train_data(prefix)
        for temp_model_dis in new_cluster_distribution:
            num_active = sum(temp_model_dis[2])
            temp_model_dis.append(num_active)
            sum_model_num_active = sum_model_num_active + num_active
            if num_active > config.fine_lower_limit:
                # Fine tuning
                print(f"Fine tuning model for {i} time...")
                df_train_data = df_group_train_data.get_group(temp_model_dis[0]) 
                df_train_data = df_train_data.drop('model', axis = 1)
                train_data = df_train_data.to_numpy(dtype = str)
                iter_train_specific_prefix(prefix, temp_model_dis[0], len(temp_model_dis[2]), train_data)


        temp_buget = sum_model_num_active
        if temp_buget > realtime_budget:
            growth_factor = realtime_budget / temp_buget
        elif temp_buget * config.growth_factor > realtime_budget:
            growth_factor = realtime_budget / temp_buget
        else:
            growth_factor = config.growth_factor
        
        for temp_model_dis in new_cluster_distribution:
            temp_model_dis[3] = temp_model_dis[3] * growth_factor
        
        print('After each model is assigned a budget: ', new_cluster_distribution)
        model_path = config.iter_model_path
        # print("intput: ", new_cluster_distribution)
        hit_rate, hit_rate_no_alias, list_alias_prefix, generated_address_num, generated_address_num_after_del_alias, new_cluster_distribution = \
                        init_probe_specific_prefix(prefix, test_prefix, new_cluster_distribution, model_path, sum_alias_prefix)
        # print("output: ", new_cluster_distribution)
        record_new_cluster_distribution = copy.deepcopy(new_cluster_distribution)
        iter_info_record.append([prefix, test_prefix, hit_rate, hit_rate_no_alias, list_alias_prefix,generated_address_num,  \
                        generated_address_num_after_del_alias, record_new_cluster_distribution, realtime_budget])

        #updata
        # num_active = sum(new_cluster_distribution)
        sum_num_active = sum_model_num_active + sum_num_active
        sum_generated_address_num = sum_generated_address_num + generated_address_num
        sum_alias_prefix = list(set(sum_alias_prefix + list_alias_prefix))
        realtime_budget = realtime_budget - generated_address_num
    # print("remaining budget:", realtime_budget)
    if sum_generated_address_num != 0:
        iter_info_record.append(['all:', sum_num_active, sum_generated_address_num, round(100*sum_num_active/sum_generated_address_num, 2), realtime_budget])
    else:
        iter_info_record.append(['all:', sum_num_active, sum_generated_address_num, 0, realtime_budget])
    df_prefix_hit_alias = pd.DataFrame(data=iter_info_record,
                                    columns=['prefix', 'test_prefix', 'hit_rate', 'hit_rate_no_alias', 'alias_prefix', 'num_init_probe_address','generated_address_num_after_del_alias','cluster_distribution', 'realtime_budget'])
    path = config.zmap_result_path + '{prefix}_iter_prob_info.txt'.format(prefix=prefix)
    df_prefix_hit_alias.to_csv(path, index=False)   
    print(f"---------end---------- iter prob prefix for {prefix} ...")   
    return realtime_budget


def iter_probe_all_model():
    df_prefix_hit_alias = get_init_prob_cluster_distribution()
    prefix_list = df_prefix_hit_alias['prefix'].to_list()

    remaining_budget = 0

    for prefix in prefix_list:
        iter_info_record = df_prefix_hit_alias[df_prefix_hit_alias['prefix'] == prefix].values.tolist()
        init_prob_record = iter_info_record[0]
        budget = init_prob_record[8] + remaining_budget
        test_prefix = init_prob_record[1]
        remaining_budget = iter_probe_specific_prefix(prefix, test_prefix, budget, iter_info_record)


# main 

def main():
    # init prob 
    init_probe_all_model()

    # iter prob
    iter_probe_all_model()
    

if __name__ == '__main__':
    main()
