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

def creat_map(ax, leftlon, rightlon, lowerlat, upperlat, numblon, numblat, xminor, yminor, strsize, chooseterm):
    if chooseterm == 1:
        ax.add_feature(cfeat.LAND.with_scale('110m'),facecolor='0.75',edgecolor='black',linewidth=0.3,zorder=6)
    elif chooseterm == 2:
        ax.add_feature(cfeat.COASTLINE.with_scale('110m'), linewidth=0.3,zorder=0)
    ax.set_extent([leftlon, rightlon, lowerlat, upperlat],crs=ccrs.PlateCarree())
    ax.set_xticks(np.arange(leftlon,rightlon+1,numblon),crs=ccrs.PlateCarree(),)
    ax.xaxis.set_minor_locator(plt.MultipleLocator(xminor))
    ax.set_yticks(np.arange(lowerlat,upperlat+1,numblat),crs=ccrs.PlateCarree(),)
    ax.yaxis.set_minor_locator(plt.MultipleLocator(yminor))
    ax.tick_params(labelsize = strsize)
    lon_formatter = cticker.LongitudeFormatter()
    lat_formatter = cticker.LatitudeFormatter()
    ax.xaxis.set_major_formatter(lon_formatter)
    ax.yaxis.set_major_formatter(lat_formatter)
    return ax
