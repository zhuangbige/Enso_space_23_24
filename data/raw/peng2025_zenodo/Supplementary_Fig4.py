
import sys
sys.path.append(r'C:\Program Files\python')
print(sys.path)
import matplotlib as mpl
import h5py
import numpy as np
import xarray as xr
import matplotlib as mpl
from scipy import signal
from scipy.signal import convolve2d
from scipy import stats
from scipy.interpolate import interp2d
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeat
import cartopy.mpl.ticker as cticker
from creat_mapnoproj import*
import cmaps
from matplotlib.ticker import MultipleLocator, FormatStrFormatter
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.colors as colors
from matplotlib.colors import ListedColormap
import scipy.io as scio
from cartopy.util import add_cyclic_point
from mpl_toolkits.basemap import Basemap

mat_contents = scio.loadmat(r'Yourpath\Supplementary_Fig4.mat')
for var_name, var_value in mat_contents.items():
    exec(f'{var_name} = var_value')
fig = plt.figure(figsize=(18,7))
ax1=fig.add_subplot(121)
fig.subplots_adjust(wspace=0.19,hspace=0.25)
xmajorLocator = MultipleLocator(2) 
xmajorFormatter = FormatStrFormatter('%5.0f')
xminorLocator = MultipleLocator(1)
ymajorLocator = MultipleLocator(0.5) 
ymajorFormatter = FormatStrFormatter('%5.1f')
yminorLocator = MultipleLocator(0.1)  
line1 =ax1.plot(np.squeeze(time),np.squeeze(sstafor2023nino3plot[:,0]),color='gray',linewidth=2.5, label='Jan01')
line1 =ax1.plot(np.squeeze(time),np.squeeze(sstafor2023nino3plot[:,1]),color='peru',linewidth=2.5, label='Feb01')
line1 =ax1.plot(np.squeeze(time),np.squeeze(sstafor2023nino3plot[:,2]),color='green',linewidth=2.5, label='Mar01')
line1 =ax1.plot(np.squeeze(time),np.squeeze(sstafor2023nino3plot[:,3]),color='red',linewidth=2.5, label='Apr01')
line1 =ax1.plot(np.squeeze(time),np.squeeze(sstafor2023nino3plot[:,4]),color='m',linewidth=2.5, label='May01')
line1 =ax1.plot(np.squeeze(time),np.squeeze(sstafor2023nino3plot[:,5]),color='b',linewidth=2.5, label='Jun01')
line1 =ax1.plot(np.squeeze(time),np.squeeze(sstafor2023nino3plot[:,6]),color='cyan',linewidth=2.5, label='Jul01')
line1 =ax1.plot(np.squeeze(time),np.squeeze(sstafor2023nino3plot[:,7]),color='royalblue',linewidth=2.5, label='Aug01')
line1 =ax1.plot(np.squeeze(time),np.squeeze(sstafor2023nino3plot[:,8]),color='darkorange',linewidth=2.5, label='Sep01')
line1 =ax1.plot(np.squeeze(time),np.squeeze(oisstsince1982anomnino32023[:,0]),color='black',linewidth=2.5, label='Obs')
ax1.legend(loc='upper left', frameon=True,fontsize=12) 
ax1.axhline(y=0, c='grey', ls='--', lw=2)   
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.set_title('a. Niño 3 SSTA (°C)',loc='left',fontsize=16)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set_xticks(np.arange(1,19.01,2))
ax1.set_xticklabels(["Feb","Apr","Jun","Aug","Oct","Dec","Feb(1)","Apr(1)","Jun(1)","Aug(1)"])
ax1.set(xlim=(0.0, 17), ylim=(-1, 2.2),
       xlabel=' ', ylabel=' ',
       title=' ')

ax1=fig.add_subplot(122)
fig.subplots_adjust(wspace=0.19,hspace=0.25)
xmajorLocator = MultipleLocator(2) 
xmajorFormatter = FormatStrFormatter('%5.0f')
xminorLocator = MultipleLocator(1)
ymajorLocator = MultipleLocator(0.5) 
ymajorFormatter = FormatStrFormatter('%5.1f')
yminorLocator = MultipleLocator(0.1)  
line1 =ax1.plot(np.squeeze(time),np.squeeze(sstafor2023nino34plot[:,0]),color='gray',linewidth=2.5, label='Jan01')
line1 =ax1.plot(np.squeeze(time),np.squeeze(sstafor2023nino34plot[:,1]),color='peru',linewidth=2.5, label='Feb01')
line1 =ax1.plot(np.squeeze(time),np.squeeze(sstafor2023nino34plot[:,2]),color='green',linewidth=2.5, label='Mar01')
line1 =ax1.plot(np.squeeze(time),np.squeeze(sstafor2023nino34plot[:,3]),color='red',linewidth=2.5, label='Apr01')
line1 =ax1.plot(np.squeeze(time),np.squeeze(sstafor2023nino34plot[:,4]),color='m',linewidth=2.5, label='May01')
line1 =ax1.plot(np.squeeze(time),np.squeeze(sstafor2023nino34plot[:,5]),color='b',linewidth=2.5, label='Jun01')
line1 =ax1.plot(np.squeeze(time),np.squeeze(sstafor2023nino34plot[:,6]),color='cyan',linewidth=2.5, label='Jul01')
line1 =ax1.plot(np.squeeze(time),np.squeeze(sstafor2023nino34plot[:,7]),color='royalblue',linewidth=2.5, label='Aug01')
line1 =ax1.plot(np.squeeze(time),np.squeeze(sstafor2023nino34plot[:,8]),color='darkorange',linewidth=2.5, label='Sep01')
line1 =ax1.plot(np.squeeze(time),np.squeeze(oisstsince1982anomnino342023[:,0]),color='black',linewidth=2.5, label='Obs')
ax1.legend(loc='upper left', frameon=True,fontsize=12) 
ax1.axhline(y=0, c='grey', ls='--', lw=2)   
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.set_title('b. Niño 3.4 SSTA (°C)',loc='left',fontsize=16)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set_xticks(np.arange(1,19.01,2))
ax1.set_xticklabels(["Feb","Apr","Jun","Aug","Oct","Dec","Feb(1)","Apr(1)","Jun(1)","Aug(1)"])
ax1.set(xlim=(0.0, 17), ylim=(-1, 2.2),
       xlabel=' ', ylabel=' ',
       title=' ')
fig.savefig(r'Yourpath\Supplementary_Fig4.pdf',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)
fig.savefig(r'Yourpath\Supplementary_Fig4.png',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)