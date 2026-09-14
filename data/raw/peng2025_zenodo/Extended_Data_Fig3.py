
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

mat_contents = scio.loadmat(r'Yourpath\Extended_Data_Fig3.mat')
for var_name, var_value in mat_contents.items():
    exec(f'{var_name} = var_value')
    
dtdtanomnino3plot=np.squeeze(dtdtanomnino3)*1e7
wtermanomnino3plot=np.squeeze(wtermanomnino3)*1e7
vadvtermanomnino3plot=np.squeeze(vadvtermanomnino3)*1e7
uadvtermanomnino3plot=np.squeeze(uadvtermanomnino3)*1e7

qnettermanomnino3plot=np.squeeze(qnettermanomnino3)*1e7
resnino3plot=np.squeeze(resnino3)*1e7

# Thermocline feedback (TH, red line), 
wterm1nino3plot=np.squeeze(wterm1nino3)*1e7
# Ekman feedback (EK, magenta line)
wterm2nino3plot=np.squeeze(wterm2nino3)*1e7
# nonlinear term
wterm3nino3plot=np.squeeze(wterm3nino3)*1e7

timeaaplot=np.squeeze(timeaa[0,0:529])
timeaaplot2=np.squeeze(timeaa[0,0:530])

fig = plt.figure(figsize=(15,7))
ax1=fig.add_subplot(121)
fig.subplots_adjust(wspace=0.19,hspace=0.25)
xmajorLocator = MultipleLocator(2/12) 
xmajorFormatter = FormatStrFormatter('%5.0f')
xminorLocator = MultipleLocator(1/12)
ymajorLocator = MultipleLocator(1) 
ymajorFormatter = FormatStrFormatter('%5.1f')
yminorLocator = MultipleLocator(0.5)
line1 =ax1.plot(timeaaplot,dtdtanomnino3plot,color='black',linewidth=2.5)
ax1.text(2023+3/12, 1.7, r"$T_t'$", color='black', fontsize=16, ha='center', va='center')
line1 =ax1.plot(timeaaplot,wtermanomnino3plot,color='red',linewidth=2.5)
ax1.text(2023+6/12+0.02, 2.8, r"-(w$T_z)'$", color='red', fontsize=16, ha='center', va='center')
line1 =ax1.plot(timeaaplot,vadvtermanomnino3plot,color='m',linewidth=2.5)
ax1.text(2023+5/12, 0.9, r"-(v$T_y)'$", color='m', fontsize=16, ha='center', va='center')
line1 =ax1.plot(timeaaplot,uadvtermanomnino3plot,color='cyan',linewidth=2.5)
ax1.text(2023+10/12, -0.5, r"-(u$T_x)'$", color='cyan', fontsize=16, ha='center', va='center')
line1 =ax1.plot(timeaaplot,qnettermanomnino3plot,color='b',linewidth=2.5)
ax1.text(2023+8/12, -1.5, r"$Q'$", color='b', fontsize=16, ha='center', va='center')
line1 =ax1.plot(timeaaplot,resnino3plot,color='gray',linewidth=1)
ax1.text(2023+6/12, -0.7, r"$Res'$", color='gray', fontsize=16, ha='center', va='center')
ax1.axhline(y=0, c='grey', ls='--', lw=2)   
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.set(xlim=(2023.0, 2024), ylim=(-2.5, 3.5),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('a. Heat budget (10$^{-7}$°C/s)',loc='left',fontsize=16)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set_xticks(np.arange(2023+1/12,2024.01,2/12))
ax1.set_xticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])

ax1=fig.add_subplot(122)
fig.subplots_adjust(wspace=0.19,hspace=0.25) 
line1 =ax1.plot(timeaaplot,wtermanomnino3plot,color='black',linewidth=2.5)
ax1.text(2023+6/12+0.02, 2.8, r"-(w$T_z)'$", color='black', fontsize=16, ha='center', va='center')
line1 =ax1.plot(timeaaplot2,wterm1nino3plot,color='red',linewidth=2.5)
ax1.text(2023+6/12+0.00, 1.8, r"-$\overline{w}$$T_z'$", color='red', fontsize=16, ha='center', va='center')
line1 =ax1.plot(timeaaplot2,wterm2nino3plot,color='m',linewidth=2.5)
ax1.text(2023+5/12, 1.1, r"-w'$\overline{T}_z$", color='m', fontsize=16, ha='center', va='center')
line1 =ax1.plot(timeaaplot2,wterm3nino3plot,color='b',linewidth=2.5)
ax1.text(2023+11/12, -1.0, r"-w'$T_z'$", color='b', fontsize=16, ha='center', va='center')
ax1.axhline(y=0, c='grey', ls='--', lw=2)    
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.set(xlim=(2023.0, 2024), ylim=(-2.5, 3.5),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('b. w term (10$^{-7}$°C/s)',loc='left',fontsize=16)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set_xticks(np.arange(2023+1/12,2024.01,2/12))
ax1.set_xticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
fig.savefig(r'Yourpath\Extended_Data_Fig3.pdf',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)
fig.savefig(r'Yourpath\Extended_Data_Fig3.png',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)   