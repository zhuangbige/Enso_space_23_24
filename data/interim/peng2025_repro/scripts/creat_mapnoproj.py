# -*- coding: utf-8 -*-
"""
Created on Thu Mar 19 18:16:25 2020

@author: Zaamlam Leung
"""

import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeat
import cartopy.mpl.ticker as cticker

# 创造地图

def creat_mapnoproj(ax, leftlon, rightlon, lowerlat, upperlat, numblon, numblat, xminor, yminor, strsize, chooseterm):
    ax.set_extent([leftlon, rightlon, lowerlat, upperlat])
    ax.set_xticks(np.arange(leftlon,rightlon+1,numblon))
    ax.xaxis.set_minor_locator(plt.MultipleLocator(xminor))
    ax.set_yticks(np.arange(lowerlat,upperlat+1,numblat))
    ax.yaxis.set_minor_locator(plt.MultipleLocator(yminor))
    ax.tick_params(labelsize = strsize)
    lon_formatter = cticker.LongitudeFormatter()
    lat_formatter = cticker.LatitudeFormatter()
    ax.xaxis.set_major_formatter(lon_formatter)
    ax.yaxis.set_major_formatter(lat_formatter)
    return ax
