from taiko.config import *
from taiko.play import *
from taiko.deprecated.primitive import *
from collections import deque

import re
import pandas as pd
import numpy as np
from sklearn import preprocessing
from scipy.stats import mode
from imblearn.over_sampling import SMOTE

__all__ = ['get_performance', 'do_over_sampled', 'do_scaling']


class _Performance(object):
    """
    Handle the specific play and engineer features around hit events.

    :protected attributes:
        event_primitive_df: dataframe containing of primitives around events in this play.

        note_df: drum note dataframe of the particular song
        play: dataframe about particular arms of the record

        events: the 2D array which element (time, label) represents a note type "label" occurs at "time"
        time_unit: the minimum time interval between two notes depending on BPM of a song
        bar_unit: default is "time_unit x 8"
        delta_t: time interval we consider a local event
    """

    def __init__(self, who_id, song_id, order_id, scale, resample):
        self._event_primitive_df = None

        self._note_df = load_note_df(who_id, song_id, order_id)
        self._play = get_play(who_id, song_id, order_id, resample=resample)

        self._events = self._play.events
        self._time_unit = mode(self._note_df['time_unit'])[0]
        self._delta_t = self._time_unit

        self.__build_event_primitive_df()

        if scale:
            self._event_primitive_df = do_scaling(self._event_primitive_df)

    def __build_event_primitive_df(self):
        """
        After setting play's dataframe, build dataframe of primitives around events in this play.

        :return: feature engineered dataframe of primitives
        """

        labels = [label for label, _ in self._play.play_dict.items()]
        windows = [deque() for _ in range(len(self._play.play_dict))]
        play_ids = [0] * len(self._play.play_dict)
        play_mats = [play_df.values for _, play_df in self._play.play_dict.items()]

        tmp_primitive_mat = []
        # split all event times with gap "delta_t"
        for id_, _ in enumerate(self._events):
            event_time = self._events[id_][0]
            hit_type = self._events[id_][1]
            local_start_time = event_time - self._delta_t / 2
            local_end_time = event_time + self._delta_t / 2

            for i_ in range(len(self._play.play_dict)):
                # slide window
                if len(windows[i_]) == 0 and play_ids[i_] < len(play_mats[i_]):
                    windows[i_].append(play_mats[i_][play_ids[i_]])
                    play_ids[i_] += 1

                while play_ids[i_] < len(play_mats[i_]) and play_mats[i_][play_ids[i_]][0] < local_end_time:
                    windows[i_].append(play_mats[i_][play_ids[i_]])
                    play_ids[i_] += 1

                while len(windows[i_]) > 0 and windows[i_][0][0] < local_start_time:
                    windows[i_].popleft()

            feature_row = [hit_type] + get_features(windows)
            tmp_primitive_mat.append(feature_row)

        columns = get_feature_columns(labels)
        event_primitive_df = pd.DataFrame(data=tmp_primitive_mat,
                                          columns=['hit_type'] + columns)

        near_df = self.__get_near_event_hit_type()
        event_primitive_df = pd.concat([event_primitive_df, near_df], axis=1)
        self._event_primitive_df = event_primitive_df

    def __get_near_event_hit_type(self, n_counts=2):
        """
        Get event hit type before and after the current hit type.

        :param n_counts: range to get hit types
        :return: the dataframe contains all hit types
        """

        mat = []

        for id_ in range(len(self._events)):
            near = []

            for i_ in range(n_counts):
                hit_type = 0
                if id_ - 1 - i_ >= 0:
                    hit_type = self._events[id_ - 1 - i_][1]
                near.append(hit_type)

            for i_ in range(n_counts):
                hit_type = 0
                if id_ + 1 + i_ < len(self._events):
                    hit_type = self._events[id_ + 1 + i_][1]
                near.append(hit_type)

            mat.append(near)

        near_df = pd.DataFrame(data=mat,
                               columns=['L' + str(i_ + 1) for i_ in range(n_counts)] +
                               ['R' + str(i_ + 1) for i_ in range(n_counts)])

        return near_df

    @property
    def event_primitive_df(self):
        return self._event_primitive_df


def get_performance(who_id, song_id, order_id, scale=True, resample=True):
    """
    Get the performance.

    :param who_id: # of drummer
    :param song_id: # of song
    :param order_id: # of performance repetitively
    :param scale: if "True", scale values of required features
    :param resample: if not "None", resample by this frequency
    :return: the desired unique performance
    """

    return _Performance(who_id, song_id, order_id, scale, resample)


def do_scaling(df):
    """
    Scale values of required features.

    :return: nothing
    """

    scaler = preprocessing.StandardScaler()
    columns = df.columns
    columns = [col for col in columns if not re.match(NO_SCALE_REGEX, col)]

    subset = df[columns]
    train_x = [tuple(x) for x in subset.values]
    train_x = scaler.fit_transform(train_x)
    new_df = pd.DataFrame(data=train_x, columns=columns)
    df.update(new_df)

    return df


def do_over_sampled(df):
    x_columns, y_columns = [], []
    for col in df.columns:
        if re.match('hit_type', col):
            y_columns.append(col)
        else:
            x_columns.append(col)

    x = df.drop(y_columns, axis=1)
    y = df[y_columns]
    y = np.ravel(y)

    x_resampled, y_resampled = SMOTE(k_neighbors=3, random_state=0).fit_sample(x, y)

    x_df = pd.DataFrame(columns=x_columns, data=x_resampled)
    y_df = pd.DataFrame(columns=y_columns, data=y_resampled)

    new_df = pd.concat([x_df, y_df], axis=1)
    new_df = new_df[df.columns]

    return new_df
