
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
from creat_map import*
import cmaps
from matplotlib.ticker import MultipleLocator, FormatStrFormatter
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.colors as colors
from matplotlib.colors import ListedColormap
import scipy.io as scio
from cartopy.util import add_cyclic_point
mat_contents = scio.loadmat(r'Yourpath\Extended_Data_Fig2.mat')
for var_name, var_value in mat_contents.items():
    exec(f'{var_name} = var_value')
 
cmapcolorwithwhite=cmaps.GrayWhiteGray
newcolorwithwhite = cmapcolorwithwhite(np.linspace(0, 1, 40))

cmapcolor=cmaps.GMT_polar
newcoloraa = cmapcolor(np.linspace(0, 1, 100))
new =np. vstack((newcoloraa[10:46:1,:],newcolorwithwhite[18:23,:], newcoloraa[54:90:1,:]))
newcolor1 = ListedColormap(new)

xx1, yy1 = np.meshgrid(lon,lat)
xx2, yy2 = np.meshgrid(lon,lat)

levels1 = np.arange(-1.6,1.61,0.1) 
norm1= colors.Normalize(vmin=-2, vmax=2)


proj = ccrs.PlateCarree(central_longitude=180)  
fig = plt.figure(figsize=(12.5,11.2))
ax1=fig.add_subplot(311, projection=proj)
ax1 = creat_map(ax1, 0, 360, -60, 60,60, 20, 10, 10, 14, 1)
ctrf = ax1.contourf(xx2,yy2,oisstanom2023all[:,:],levels=levels1,extend='both',norm=norm1,
                   transform=ccrs.PlateCarree(), cmap=newcolor1)
ax1.contour(xx2,yy2, oisstanom2023all[:,:],levels=np.arange(-3.2,3.21,0.2) ,linestyles='solid',
                       transform=ccrs.PlateCarree(), colors='white',linewidths=0.1)
ax1.set_title('a. SSTA',loc='left',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.xaxis.set_major_formatter(plt.NullFormatter()) 
ax1.set(ylim=(-45, 45));

ax1=fig.add_subplot(312, projection=proj)
ax1 = creat_map(ax1, 0, 360, -60, 60,60, 15, 10, 10, 14, 1)
ctrf = ax1.contourf(xx2,yy2,oisstanom2023detrend[:,:],levels=levels1,extend='both',norm=norm1,
                   transform=ccrs.PlateCarree(), cmap=newcolor1)
ax1.contour(xx2,yy2, oisstanom2023detrend[:,:],levels=np.arange(-3.2,3.21,0.2),linestyles='solid',
                       transform=ccrs.PlateCarree(), colors='white',linewidths=0.1)
ax1.set_title('b. Detrended SSTA',loc='left',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.xaxis.set_major_formatter(plt.NullFormatter()) 
ax1.set(ylim=(-45, 45));

ax1=fig.add_subplot(313, projection=proj)
ax1 = creat_map(ax1, 0, 360, -60, 60,60, 15, 10, 10, 14, 1)
ctrf = ax1.contourf(xx2,yy2,oisstanom2023trend[:,:],levels=levels1,extend='both',norm=norm1,
                   transform=ccrs.PlateCarree(), cmap=newcolor1)
ax1.contour(xx2,yy2, oisstanom2023trend[:,:],levels=np.arange(-3.2,3.21,0.2),linestyles='solid',
                       transform=ccrs.PlateCarree(), colors='white',linewidths=0.1)
ax1.set_title('c. SST Trend',loc='left',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set(ylim=(-45, 45));

position=fig.add_axes([0.92, 0.45, 0.008, 0.14])
cb=fig.colorbar(ctrf,cax=position,orientation='vertical',
                  ticks=np.arange(-1.6,1.61,1.6),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=16)
cb.set_label(f'SSTA ($^\circ$C)', fontsize=16)

left, bottom, width, height = 0.125, -0.098, 0.778, 0.16
ax1 = fig.add_axes([left, bottom, width, height]) 
fig.subplots_adjust(wspace=0.19,hspace=0.25)
xmajorLocator = MultipleLocator(8) 
xmajorFormatter = FormatStrFormatter('%5.0f')
xminorLocator = MultipleLocator(1)
ymajorLocator = MultipleLocator(1) 
ymajorFormatter = FormatStrFormatter('%5.1f')
yminorLocator = MultipleLocator(0.5)
line1 =ax1.plot(np.squeeze(timesince1982[0,0:508]),np.squeeze(oisstsince1982anomnino3detrend),color='r',linewidth=2.5, label='Detrend')
line1 =ax1.plot(np.squeeze(timesince1982[0,0:508]),np.squeeze(oisstsince1982anomnino3trend),color='b', ls='--',linewidth=2.5, label='Trend')
ax1.axhline(y=0, c='grey', ls='--', lw=2)   
ax1.legend(loc='upper left', frameon=True,fontsize=16) 
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.set(xlim=(1982.0, 2024), ylim=(-2, 4),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('d. Nino 3 SSTA ($^\circ$C)',loc='left',fontsize=16)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.text(2023-3.9,2.6, r"2023", color='k', fontsize=13, ha='center', va='center')
xx=2023
yy=2.3
ax1.annotate('',
            xy=(xx, yy),  
            xytext=(xx-2.5, yy+0.2),  
            arrowprops=dict(facecolor='k', edgecolor='k', width=0.5, headwidth=4, shrink=0.05))
ax1.xaxis.set_major_formatter(plt.NullFormatter()) 

left, bottom, width, height = 0.125, -0.295, 0.778, 0.16
ax1 = fig.add_axes([left, bottom, width, height]) 
xmajorLocator = MultipleLocator(8) 
xmajorFormatter = FormatStrFormatter('%5.0f')
xminorLocator = MultipleLocator(1)
ymajorLocator = MultipleLocator(0.5) 
ymajorFormatter = FormatStrFormatter('%5.1f')
yminorLocator = MultipleLocator(0.1)  
line1 =ax1.plot(np.squeeze(timesince1982),np.squeeze(oisstsince1982anomNATLplot),color='red',linewidth=2.5, label='ATL')
line1 =ax1.plot(np.squeeze(timesince1982),np.squeeze(oisstsince1982anomWINDplot),color='blue',linewidth=2.5, label='IND')
ax1.axhline(y=0, c='grey', ls='--', lw=1.5)   
ax1.legend(loc='upper left', frameon=True,fontsize=16) 
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.set(xlim=(1982.0, 2024), ylim=(-1, 1.5),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('e. SSTA ($^\circ$C)',loc='left',fontsize=16)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.text(2023-3.9,1.2, r"2023", color='k', fontsize=13, ha='center', va='center')
xx=2023
yy=1.1
ax1.annotate('',
            xy=(xx, yy),  
            xytext=(xx-2.5, yy+0.15),  
            arrowprops=dict(facecolor='k', edgecolor='k', width=0.5, headwidth=4, shrink=0.05))
plt.show()
fig.savefig(r'Yourpath\Extended_Data_Fig2.pdf',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)
fig.savefig(r'Yourpath\Extended_Data_Fig2.png',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)




