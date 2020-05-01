#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
"""

__version__ = '0.0.1'

import logging
import os
import random
import sys
import numpy as np

np.set_printoptions(precision=20)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
console = logging.StreamHandler()
console.setFormatter(logging.Formatter('%(asctime)s - %(funcName)s - %(levelname)s - %(message)s'))
console.setLevel(logging.DEBUG)
logger.addHandler(console)
# logfile = logging.FileHandler(filename="log.txt")
# logfile.setFormatter(logging.Formatter('%(asctime)s - %(funcName)s - %(levelname)s - %(message)s'))
# logfile.setLevel(logging.DEBUG)
# logger.addHandler(logfile)

# import boto3
# import dateutil.parser
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from shapely.geometry import Point, Polygon
from shapely.geometry.polygon import LinearRing, LineString
from os import listdir
from os.path import isfile, join
import math
from datetime import datetime

from utils.cw_utils import *
from utils.log_analysis import *


def plot_grid_world_eval(ax, episode_df, inner, outer, scale=10.0, plot=True):
    """
    plot a scaled version of lap, along with throttle taken a each position
    """
    stats = []
    outer = [(val[0] / scale, val[1] / scale) for val in outer]
    inner = [(val[0] / scale, val[1] / scale) for val in inner]
    max_x = int(np.max([val[0] for val in outer]))
    max_y = int(np.max([val[1] for val in outer]))
    # print(max_x, max_y)
    grid = np.zeros((max_x + 1, max_y + 1))

    # create shapely ring for outter and inner
    outer_polygon = Polygon(outer)
    inner_polygon = Polygon(inner)
    print('Outer polygon length = %.2f (meters)' % (outer_polygon.length / scale))
    print('Inner polygon length = %.2f (meters)' % (inner_polygon.length / scale))

    dist = 0.0
    for ii in range(1, len(episode_df)):
        dist += math.sqrt((episode_df['x'].iloc[ii] - episode_df['x'].iloc[ii - 1]) ** 2 + (
                    episode_df['y'].iloc[ii] - episode_df['y'].iloc[ii - 1]) ** 2)
    dist /= 100.0

    t0 = datetime.fromtimestamp(float(episode_df['timestamp'].iloc[0]))
    t1 = datetime.fromtimestamp(float(episode_df['timestamp'].iloc[len(episode_df) - 1]))
    lap_time = (t1 - t0).total_seconds()

    average_throttle = np.nanmean(episode_df['throttle'])
    max_throttle = np.nanmax(episode_df['throttle'])
    min_throttle = np.nanmin(episode_df['throttle'])
    velocity = dist / lap_time
    print('Distance, lap time = %.2f (meters), %.2f (sec)' % (dist, lap_time))
    print('Average throttle, velocity = %.2f (Gazebo), %.2f (meters/sec)' % (average_throttle, velocity))
    stats.append((dist, lap_time, velocity, average_throttle, min_throttle, max_throttle))

    if plot:
        for y in range(max_y):
            for x in range(max_x):
                point = Point((x, y))

                # this is the track
                if (not inner_polygon.contains(point)) and (outer_polygon.contains(point)):
                    grid[x][y] = -1.0

                # find df slice that fits into this
                df_slice = episode_df[(episode_df['x'] >= (x - 1) * scale) & (episode_df['x'] < x * scale) & \
                                      (episode_df['y'] >= (y - 1) * scale) & (episode_df['y'] < y * scale)]
                if len(df_slice) > 0:
                    # average_throttle = np.nanmean(df_slice['throttle'])
                    grid[x][y] = np.nanmean(df_slice['throttle'])

        imgplot = ax.imshow(grid)
        fig.colorbar(imgplot, orientation='vertical')
        ax.set_title('Lap time (sec) = %.2f' % lap_time)

    return lap_time, average_throttle, stats


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser(description='')
    parser.add_argument('-i', '--sim_id', default='sim-dl533hr387wm', type=str, help='')
    parser.add_argument('-t', '--track_name', default='reinvent_base', type=str, help='')
    parser.add_argument('-o', '--out', default='outputs', type=str, help='')
    args = parser.parse_args()
    # args = parser.parse_args(args=[])
    logger.info(json.dumps(args.__dict__, indent=2))
    sys.stdout.flush()

    stream_name = args.sim_id
    eval_fname = 'logs/deepracer-%s.log' % stream_name
    # download_log(eval_fname, stream_prefix=stream_name)

    # Load the training log
    eval_data = load_data(eval_fname)
    eval_df = convert_to_pandas(eval_data, None)
    logger.info(eval_df.head())
    logger.info((eval_df['x'].min(), eval_df['x'].max()))
    logger.info((eval_df['y'].min(), eval_df['y'].max()))
    logger.info((eval_df['iteration'].min(), eval_df['iteration'].max()))
    logger.info((eval_df['episode'].min(), eval_df['episode'].max()))

    # Visualize the Track and Waypoints
    ListFiles = [f for f in listdir("tracks/") if isfile(join("tracks/", f))]
    logger.info(ListFiles)
    waypoints = np.load("tracks/%s.npy" % args.track_name)
    logger.info(waypoints.shape)

    # rescale waypoints to centimeter scale
    center_line = waypoints[:, 0:2] * 100
    inner_border = waypoints[:, 2:4] * 100
    outer_border = waypoints[:, 4:6] * 100

    y_offset = int(eval_df['y'].min())
    if y_offset > 0:  # if positive, just keep it the same
        y_offset = 0
    y_offset = abs(y_offset)
    inner_border[:, 1] = inner_border[:, 1] + y_offset
    center_line[:, 1] = center_line[:, 1] + y_offset
    outer_border[:, 1] = outer_border[:, 1] + y_offset

    output_dir = args.out
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Grid World Analysis
    N_EPISODES = 5

    fig = plt.figure(figsize=(6 * N_EPISODES, 7 * 2))

    for e in range(N_EPISODES):
        print("Episode #%s " % e)
        episode_df = eval_df[eval_df['episode'] == e]
        if len(episode_df) > 0:
            ax = fig.add_subplot(2, N_EPISODES, 1 + e)
            plot_grid_world_eval(ax, episode_df, inner_border, outer_border, scale=5.0)
        print("###############################################################\n")

    for e in range(N_EPISODES):
        episode_df = eval_df[eval_df['episode'] == e]
        if len(episode_df) > 0:
            ax = fig.add_subplot(2, N_EPISODES, N_EPISODES + 1 + e)
            # episode_df['throttle'].plot(x='steps', y='speed', style='-', title='speed')
            episode_df['throttle'].plot.hist()

    plt.savefig(os.path.join(output_dir, "%s.png" % args.sim_id))
    # plt.show()
    plt.close()
