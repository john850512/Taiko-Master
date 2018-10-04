from .tools.singleton import *
from .image import *
from .play import *
from .config import *

import seaborn as sns
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from glob import glob
import posixpath
from skimage.io import imshow, imsave, imread
import os

__all__ = ['update_play_result']

SONGS = 4


class Database(metaclass=_Singleton):

    def __init__(self):
        self.__load_record_df()

    def __load_record_df(self):
        record_files = glob('../data/alpha/*/*/record_table.csv')
        record_dfs = []
        for record_file_path in record_files:
            record_df = pd.read_csv(record_file_path)
            record_dfs.append(record_df)
        self._record_df = pd.concat(record_dfs, ignore_index=True)

    @property
    def record_df(self):
        return self._record_df


def update_play_result(verbose=1):
    record_df = Database().record_df
    # only 4 songs we considered
    record_df = record_df[(record_df['song_id'] >= 1) & (record_df['song_id'] <= SONGS)]

    aggregate_dict = {}
    columns = ['drummer_name', 'song_id', 'p_order', 'capture_datetime'] + RESULT_BOARD_INFO_COLUMNS
    data = {}
    for col in columns:
        data[col] = []

    for id_, row in record_df.iterrows():
        try:
            capture_dir = row['capture_datetime']
            who_name = row['drummer_name']
            song_id = row['song_id']
            dirs = glob('../data/alpha/' + who_name + '/*/bb_capture/' + capture_dir)
            print(who_name, capture_dir)
            capture_dir_path = dirs[0]
            result = read_result_board_info(capture_dir_path)
            try:
                aggregate_dict[(who_name, song_id)]
            except KeyError:
                aggregate_dict[(who_name, song_id)] = 0

            p_order = aggregate_dict[(who_name, song_id)] + 1
            aggregate_dict[(who_name, song_id)] = p_order

            if verbose > 0:
                print('who = %s, id = %d, p_order = %d' % (who_name, id_, p_order))
                print(result)

            data['drummer_name'].append(who_name)
            data['song_id'].append(song_id)
            data['p_order'].append(p_order)
            data['capture_datetime'].append(capture_dir)
            for col in result.keys():
                data[col].append(result[col])

        except Exception as e:
            print(e)

    play_result_df = pd.DataFrame(data=data)
    play_result_df.to_csv('../data/taiko_tables/taiko_play_result.csv', index=False)


def update_score_auc(verbose=1):
    record_df = Database().record_df

    # only 4 songs we considered
    record_df = record_df[(record_df['song_id'] >= 1) & (record_df['song_id'] <= SONGS)]

    auc_dict = {}
    for i_ in range(SONGS):
        auc_dict[i_ + 1] = []

    try:
        for id_, row in record_df.iterrows():
            if id_ > 5:
                break
            capture_dir = row['capture_datetime']
            who_name = row['drummer_name']
            song_id = row['song_id']
            dirs = glob('../data/alpha/' + who_name + '/*/bb_capture/' + capture_dir)
            capture_dir_path = dirs[0]
            result = read_result_board_info(capture_dir_path)

            if verbose > 0:
                print(who_name, capture_dir)
                print(result)

            if result['bad'] > 0:
                continue

            auc = get_play_score_auc(capture_dir_path, song_id)
            auc_dict[song_id].append(auc)

        fc_auc_df = pd.DataFrame()
        fc_auc_df['song_id'] = [i + 1 for i in range(SONGS)]
        fc_auc_df['auc'] = [np.mean(auc_dict[i_ + 1]) for i_ in range(SONGS)]

        fc_auc_df.to_csv('../data/taiko_tables/taiko_fc_auc.csv', index=False)

    except Exception as e:
        print(e)
