from .tools.singleton import *
from .image import *
from .config import *

import pandas as pd
import numpy as np
from glob import glob
import sys

__all__ = ['create_play_result',
           'get_score_auc_stat',
           'get_best_score_board_info',
           'get_play_score_auc',
           'estimate_remained_play_times']

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


def create_play_result(verbose=1):
    record_df = Database().record_df

    # only 4 songs we considered
    record_df = record_df[(record_df['song_id'] >= 1) & (record_df['song_id'] <= SONGS)]

    aggregate_dict = {}
    columns = ['drummer_name', 'song_id', 'p_order', 'capture_datetime', 'auc'] + RESULT_BOARD_INFO_COLUMNS
    data = {}
    for col in columns:
        data[col] = []

    for id_, row in record_df.iterrows():
        try:
            capture_dir = row['capture_datetime']
            who_name = row['drummer_name']
            song_id = row['song_id']
            dirs = glob('../data/alpha/' + who_name + '/*/bb_capture/' + capture_dir)
            capture_dir_path = dirs[0]
            result = read_result_board_info(capture_dir_path)

            # increment p_order
            try:
                aggregate_dict[(who_name, song_id)]
            except KeyError:
                aggregate_dict[(who_name, song_id)] = 0

            p_order = aggregate_dict[(who_name, song_id)] + 1
            aggregate_dict[(who_name, song_id)] = p_order

            auc = get_play_score_auc(capture_dir_path, song_id)

            data['drummer_name'].append(who_name)
            data['song_id'].append(song_id)
            data['p_order'].append(p_order)
            data['capture_datetime'].append(capture_dir)
            data['auc'].append(auc)

            for col in result.keys():
                data[col].append(result[col])

            if verbose > 0:
                message = 'who_name = %s, song_id = %d, p_order = %d, %s, auc = %.4f\n' \
                          'result = %s' % \
                          (who_name, song_id, p_order, capture_dir, auc, str(result))
                sys.stdout.write(message)
                sys.stdout.flush()

        except Exception as e:
            print(e)

    play_result_df = pd.DataFrame(data=data)
    play_result_df.to_csv(PLAY_RESULT_TABLE_PATH, index=False, float_format='%.4f')


def get_score_auc_stat(song_id):
    play_result_df = pd.read_csv(PLAY_RESULT_TABLE_PATH)
    df = play_result_df[(play_result_df['song_id'] == song_id)]
    full_combo_df = df[df['bad'] == 0]
    fc_mean_auc = np.mean(full_combo_df['auc'])

    dif_auc = []
    for id_, row in df.iterrows():
        auc = row['auc']
        dif_auc.append(auc - fc_mean_auc)
    std_auc = np.std(dif_auc, ddof=1)

    return {'fc_mean_auc': fc_mean_auc,
            'std_auc': std_auc}


def get_best_score_board_info(song_id):
    play_result_df = pd.read_csv(PLAY_RESULT_TABLE_PATH)
    df = play_result_df[(play_result_df['song_id'] == song_id)]
    max_idx = df['score'].idxmax()
    row = df.loc[max_idx]
    print(row)

    capture_dir = row['capture_datetime']
    who_name = row['drummer_name']

    dirs = glob(posixpath.join(HOME_PATH, who_name + '/*/bb_capture/' + capture_dir))
    capture_dir_path = dirs[0]

    return read_score_board_info(capture_dir_path, song_id)


def get_play_score_auc(capture_dir_path=None, song_id=None, timestamps=None, img_scores=None):
    if timestamps is None and img_scores is None:
        if capture_dir_path is None or song_id is None:
            raise ValueError('Pass parameter \"capture_dir_path\" and \"song_id\".')
        timestamps, img_scores = read_score_board_info(capture_dir_path, song_id)

    area = 0.0
    for i_ in range(len(timestamps)):
        if i_ == 0:
            continue
        area += (timestamps[i_] - timestamps[i_ - 1]) * img_scores[i_ - 1]
    area /= len(timestamps)

    return area


def estimate_remained_play_times(song_id, capture_dir_path=None, auc=None):
    if auc is None:
        if capture_dir_path is None:
            raise ValueError('Pass parameter \"capture_dir_path\".')
        auc = get_play_score_auc(capture_dir_path, song_id)

    stat = get_score_auc_stat(song_id)
    factor = (auc - stat['fc_mean_auc']) / stat['std_auc']
    times = 0
    if factor < 0:
        times = int(np.ceil(-factor * 2))
    return times
