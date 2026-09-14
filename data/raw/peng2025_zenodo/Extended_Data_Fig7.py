
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

mat_contents = scio.loadmat(r'Yourpath\Extended_Data_Fig7.mat')
for var_name, var_value in mat_contents.items():
    exec(f'{var_name} = var_value')
    
xx2, yy2 = np.meshgrid(lon,depth)
cmapcolorwithwhite=cmaps.GrayWhiteGray
newcolorwithwhite = cmapcolorwithwhite(np.linspace(0, 1, 40))
cmapcolor=cmaps.GMT_polar
newcoloraa = cmapcolor(np.linspace(0, 1, 100))
new =np. vstack((newcoloraa[5:46:2,:],newcolorwithwhite[18:23,:], newcoloraa[55:95:2,:]))
newcolor1 = ListedColormap(new)

levels1 = np.arange(-4.0,4.01,0.4) 
norm1= colors.Normalize(vmin=-4.0, vmax=4.0)
fig = plt.figure(figsize=(22.5,10.8))
fig.subplots_adjust(wspace=0.14,hspace=0.17)
ymajorLocator = MultipleLocator(50) 
ymajorFormatter = FormatStrFormatter('%1.0f')
yminorLocator = MultipleLocator(10)
xmajorLocator = MultipleLocator(20) 
xmajorFormatter = FormatStrFormatter('%1.0f')
xminorLocator = MultipleLocator(10)
ax1=fig.add_subplot(241)
ctrf = ax1.contourf(xx2,yy2,tempCTRL2023anomeqJFM,levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,tempCTRL2023anomeqJFM,levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqCTRLclimJFM),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqCTRL2023JFM),color='black',linewidth=2.5)
ax1.set_title('a. JFM  ',loc='left',fontsize=16)
ax1.set_title('CTRL',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_major_formatter(ymajorFormatter)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_major_formatter(xmajorFormatter)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.set_xticks(np.arange(120,291,40))
ax1.set_xticklabels(["120E","160E","160W","120W","80W"])
ax1.set_ylabel('Depth', fontsize=16);
ax1.set(xlim=(120, 280), ylim=(250, 5)); 
ax1.xaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(242)
ctrf = ax1.contourf(xx2,yy2,tempInitApr2023anomeqAMJ,levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,tempInitApr2023anomeqAMJ,levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqCTRLclimAMJ),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqInitApr2023AMJ),color='black',linewidth=2.5)
ax1.set_title('b. AMJ  ',loc='left',fontsize=16)
ax1.set_title('InitApr2023',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_major_formatter(ymajorFormatter)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_major_formatter(xmajorFormatter)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.set_xticks(np.arange(120,291,40))
ax1.set_xticklabels(["120E","160E","160W","120W","80W"])
ax1.set(xlim=(120, 280), ylim=(250, 5)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.xaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(243)
ctrf = ax1.contourf(xx2,yy2,tempInitApr2023anomeqJAS,levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,tempInitApr2023anomeqJAS,levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqCTRLclimJAS),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqInitApr2023JAS),color='black',linewidth=2.5)
ax1.set_title('c. JAS  ',loc='left',fontsize=16)
ax1.set_title('InitApr2023',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_major_formatter(ymajorFormatter)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_major_formatter(xmajorFormatter)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.set_xticks(np.arange(120,291,40))
ax1.set_xticklabels(["120E","160E","160W","120W","80W"])
ax1.set(xlim=(120, 280), ylim=(250, 5)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.xaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(244)
ctrf = ax1.contourf(xx2,yy2,tempInitApr2023anomeqOND,levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,tempInitApr2023anomeqOND,levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqCTRLclimOND),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqInitApr2023OND),color='black',linewidth=2.5)
ax1.set_title('d. OND  ',loc='left',fontsize=16)
ax1.set_title('InitApr2023',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_major_formatter(ymajorFormatter)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_major_formatter(xmajorFormatter)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.set_xticks(np.arange(120,291,40))
ax1.set_xticklabels(["120E","160E","160W","120W","80W"])
ax1.set(xlim=(120, 280), ylim=(250, 5)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.xaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(245)
ctrf = ax1.contourf(xx2,yy2,tempCTRLEXTREMEanomeqJFM,levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,tempCTRLEXTREMEanomeqJFM,levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqCTRLclimJFM),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqCTRLEXTREMEJFM),color='black',linewidth=2.5)
ax1.set_title('e. JFM ',loc='left',fontsize=16)
ax1.set_title('CTRL',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_major_formatter(ymajorFormatter)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_major_formatter(xmajorFormatter)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.set_xticks(np.arange(120,291,40))
ax1.set_xticklabels(["120E","160E","160W","120W","80W"])
ax1.set_ylabel('Depth', fontsize=16);
ax1.set(xlim=(120, 280), ylim=(250, 5)); 

ax1=fig.add_subplot(246)
ctrf = ax1.contourf(xx2,yy2,tempInitAprEXTREMEanomeqAMJ,levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,tempInitAprEXTREMEanomeqAMJ,levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqCTRLclimAMJ),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqInitAprEXTREMEAMJ),color='black',linewidth=2.5)
ax1.set_title('f. AMJ ',loc='left',fontsize=16)
ax1.set_title('InitAprOther',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_major_formatter(ymajorFormatter)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_major_formatter(xmajorFormatter)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.set_xticks(np.arange(120,291,40))
ax1.set_xticklabels(["120E","160E","160W","120W","80W"])
ax1.set(xlim=(120, 280), ylim=(250, 5)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(247)
ctrf = ax1.contourf(xx2,yy2,tempInitAprEXTREMEanomeqJAS,levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,tempInitAprEXTREMEanomeqJAS,levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqCTRLclimJAS),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqInitAprEXTREMEJAS),color='black',linewidth=2.5)
ax1.set_title('g. JAS ',loc='left',fontsize=16)
ax1.set_title('InitAprOther',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_major_formatter(ymajorFormatter)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_major_formatter(xmajorFormatter)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.set_xticks(np.arange(120,291,40))
ax1.set_xticklabels(["120E","160E","160W","120W","80W"])
ax1.set(xlim=(120, 280), ylim=(250, 5)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(248)
ctrf = ax1.contourf(xx2,yy2,tempInitAprEXTREMEanomeqOND,levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,tempInitAprEXTREMEanomeqOND,levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqCTRLclimOND),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqInitAprEXTREMEOND),color='black',linewidth=2.5)
ax1.set_title('h. OND ',loc='left',fontsize=16)
ax1.set_title('InitAprOther',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_major_formatter(ymajorFormatter)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_major_formatter(xmajorFormatter)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.set_xticks(np.arange(120,291,40))
ax1.set_xticklabels(["120E","160E","160W","120W","80W"])
ax1.set(xlim=(120, 280), ylim=(250, 5)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
position=fig.add_axes([0.40, 0.05, 0.2, 0.012])
cb=fig.colorbar(ctrf,cax=position,orientation='horizontal',
                  ticks=np.arange(-4,4.01,2),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=16)
cb.set_label(f'Temp (°C)', fontsize=16)
fig.savefig(r'Yourpath\Extended_Data_Fig7.png',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)
fig.savefig(r'Yourpath\Extended_Data_Fig7.pdf',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)