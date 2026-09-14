
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

mat_contents = scio.loadmat(r'Yourpath\Extended_Data_Fig6.mat')
for var_name, var_value in mat_contents.items():
    exec(f'{var_name} = var_value')
xx1, yy1 = np.meshgrid(lon,lat)
levels1 = np.arange(-0.2,0.21,0.02) 
levels1a = np.arange(0.5,5,0.5)
levels1b = np.arange(-5,-0.49,0.5)
norm1= colors.Normalize(vmin=-0.2, vmax=0.2)

cmapcolorwithwhite=cmaps.GrayWhiteGray
newcolorwithwhite = cmapcolorwithwhite(np.linspace(0, 1, 40))
cmapcolor=cmaps.GMT_polar
newcoloraa = cmapcolor(np.linspace(0, 1, 100))
new =np. vstack((newcoloraa[1:45:1,:],newcolorwithwhite[18:23,:], newcoloraa[55:99:1,:]))
newcolor1 = ListedColormap(new)


fig = plt.figure(figsize=(15.0,20.0))
fig.subplots_adjust(wspace=0.14,hspace=0.19)
xmajorLocator = MultipleLocator(20) 
xmajorFormatter = FormatStrFormatter('%5.0f')
xminorLocator = MultipleLocator(5)
ymajorLocator = MultipleLocator(10) 
ymajorFormatter = FormatStrFormatter('%5.1f')
yminorLocator = MultipleLocator(2)
proj = ccrs.PlateCarree(central_longitude=180)  
ax1=fig.add_subplot(421)
mmm=np.arange(1,4,1)
ctrf = ax1.contourf(xx1,yy1,np.transpose(np.nanmean(slaanom2023[:, :, mmm-1], axis=2)),levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,np.transpose(np.nanmean(slaanom2023[:, :, mmm-1], axis=2)),levels=levels1,
                        colors='white',linestyles='solid',linewidths=0.3)
ax1.contour(xx1,yy1,np.transpose(np.nanmean(sstanom2023[:, :, mmm-1], axis=2)),levels=levels1a,
                        colors='black',linestyles='solid',linewidths=1)
ax1.contour(xx1,yy1,np.transpose(np.nanmean(sstanom2023[:, :, mmm-1], axis=2)),levels=levels1b,
                        colors='gray',linestyles='solid',linewidths=1)
ax1.plot(clx,cly,c='grey',linewidth=1)
ax1.set(xlim=(120.0, 290.0), ylim=(-25, 25),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('a. SLA & SSTA (CTRL)',loc='left',fontsize=16)
ax1.set_title('2023: JFM',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set_xticks(np.arange(140,280.1,40));
ax1.set_xticklabels(['140 E','180','140 W','100 W'],fontsize=16);
ax1.set_yticks(np.arange(-20,20.1,10));
ax1.set_yticklabels(['20 S','10 S','Eq','10 N','20 N'],fontsize=16);
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(423)
mmm=np.arange(1,4,1)
ctrf = ax1.contourf(xx1,yy1,np.transpose(np.nanmean(slaanominit2023[:, :, mmm-1], axis=2)),levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,np.transpose(np.nanmean(slaanominit2023[:, :, mmm-1], axis=2)),levels=levels1,
                        colors='white',linestyles='solid',linewidths=0.3)
ax1.contour(xx1,yy1,np.transpose(np.nanmean(sstanominit2023[:, :, mmm-1], axis=2)),levels=levels1a,
                        colors='black',linestyles='solid',linewidths=1)
ax1.contour(xx1,yy1,np.transpose(np.nanmean(sstanominit2023[:, :, mmm-1], axis=2)),levels=levels1b,
                        colors='gray',linestyles='solid',linewidths=1)
ax1.plot(clx,cly,c='grey',linewidth=1)
ax1.set(xlim=(120.0, 290.0), ylim=(-25, 25),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('c. SLA & SSTA (InitApr2023)',loc='left',fontsize=16)
ax1.set_title('AMJ',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set_xticks(np.arange(140,280.1,40));
ax1.set_xticklabels(['140 E','180','140 W','100 W'],fontsize=16);
ax1.set_yticks(np.arange(-20,20.1,10));
ax1.set_yticklabels(['20 S','10 S','Eq','10 N','20 N'],fontsize=16);
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(425)
mmm=np.arange(4,7,1)
ctrf = ax1.contourf(xx1,yy1,np.transpose(np.nanmean(slaanominit2023[:, :, mmm-1], axis=2)),levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,np.transpose(np.nanmean(slaanominit2023[:, :, mmm-1], axis=2)),levels=levels1,
                        colors='white',linestyles='solid',linewidths=0.3)

ax1.contour(xx1,yy1,np.transpose(np.nanmean(sstanominit2023[:, :, mmm-1], axis=2)),levels=levels1a,
                        colors='black',linestyles='solid',linewidths=1)
ax1.contour(xx1,yy1,np.transpose(np.nanmean(sstanominit2023[:, :, mmm-1], axis=2)),levels=levels1b,
                        colors='gray',linestyles='solid',linewidths=1)
ax1.plot(clx,cly,c='grey',linewidth=1)
ax1.set(xlim=(120.0, 290.0), ylim=(-25, 25),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('e. SLA & SSTA (InitApr2023)',loc='left',fontsize=16)
ax1.set_title('JAS',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set_xticks(np.arange(140,280.1,40));
ax1.set_xticklabels(['140 E','180','140 W','100 W'],fontsize=16);
ax1.set_yticks(np.arange(-20,20.1,10));
ax1.set_yticklabels(['20 S','10 S','Eq','10 N','20 N'],fontsize=16);
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(427)
mmm=np.arange(7,10,1)
ctrf = ax1.contourf(xx1,yy1,np.transpose(np.nanmean(slaanominit2023[:, :, mmm-1], axis=2)),levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,np.transpose(np.nanmean(slaanominit2023[:, :, mmm-1], axis=2)),levels=levels1,
                        colors='white',linestyles='solid',linewidths=0.3)
ax1.contour(xx1,yy1,np.transpose(np.nanmean(sstanominit2023[:, :, mmm-1], axis=2)),levels=levels1a,
                        colors='black',linestyles='solid',linewidths=1)
ax1.contour(xx1,yy1,np.transpose(np.nanmean(sstanominit2023[:, :, mmm-1], axis=2)),levels=levels1b,
                        colors='gray',linestyles='solid',linewidths=1)
ax1.plot(clx,cly,c='grey',linewidth=1)
ax1.set(xlim=(120.0, 290.0), ylim=(-25, 25),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('g. SLA & SSTA (InitApr2023)',loc='left',fontsize=16)
ax1.set_title('OND',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set_xticks(np.arange(140,280.1,40));
ax1.set_xticklabels(['140 E','180','140 W','100 W'],fontsize=16);
ax1.set_yticks(np.arange(-20,20.1,10));
ax1.set_yticklabels(['20 S','10 S','Eq','10 N','20 N'],fontsize=16);
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)

ax1=fig.add_subplot(422)
mmm=np.arange(1,4,1)
ctrf = ax1.contourf(xx1,yy1,np.transpose(np.nanmean(slaanomextreme[:, :, mmm-1], axis=2)),levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,np.transpose(np.nanmean(slaanomextreme[:, :, mmm-1], axis=2)),levels=levels1,
                        colors='white',linestyles='solid',linewidths=0.3)
ax1.contour(xx1,yy1,np.transpose(np.nanmean(sstanomextreme[:, :, mmm-1], axis=2)),levels=levels1a,
                        colors='black',linestyles='solid',linewidths=1)
ax1.contour(xx1,yy1,np.transpose(np.nanmean(sstanomextreme[:, :, mmm-1], axis=2)),levels=levels1b,
                        colors='gray',linestyles='solid',linewidths=1)
ax1.plot(clx,cly,c='grey',linewidth=1)
ax1.set(xlim=(120.0, 290.0), ylim=(-25, 25),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('b. SLA & SSTA (CTRL)',loc='left',fontsize=16)
ax1.set_title('Other: JFM',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set_xticks(np.arange(140,280.1,40));
ax1.set_xticklabels(['140 E','180','140 W','100 W'],fontsize=16);
ax1.set_yticks(np.arange(-20,20.1,10));
ax1.set_yticklabels(['20 S','10 S','Eq','10 N','20 N'],fontsize=16);
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.xaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(424)
mmm=np.arange(1,4,1)
ctrf = ax1.contourf(xx1,yy1,np.transpose(np.nanmean(slaanominitextreme[:, :, mmm-1], axis=2)),levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,np.transpose(np.nanmean(slaanominitextreme[:, :, mmm-1], axis=2)),levels=levels1,
                        colors='white',linestyles='solid',linewidths=0.3)

ax1.contour(xx1,yy1,np.transpose(np.nanmean(sstanominitextreme[:, :, mmm-1], axis=2)),levels=levels1a,
                        colors='black',linestyles='solid',linewidths=1)
ax1.contour(xx1,yy1,np.transpose(np.nanmean(sstanominitextreme[:, :, mmm-1], axis=2)),levels=levels1b,
                        colors='gray',linestyles='solid',linewidths=1)

ax1.plot(clx,cly,c='grey',linewidth=1)
ax1.set(xlim=(120.0, 290.0), ylim=(-25, 25),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('d. SLA & SSTA (InitAprOther)',loc='left',fontsize=16)
ax1.set_title('AMJ',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set_xticks(np.arange(140,280.1,40));
ax1.set_xticklabels(['140 E','180','140 W','100 W'],fontsize=16);
ax1.set_yticks(np.arange(-20,20.1,10));
ax1.set_yticklabels(['20 S','10 S','Eq','10 N','20 N'],fontsize=16);
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.xaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(426)
mmm=np.arange(4,7,1)
ctrf = ax1.contourf(xx1,yy1,np.transpose(np.nanmean(slaanominitextreme[:, :, mmm-1], axis=2)),levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,np.transpose(np.nanmean(slaanominitextreme[:, :, mmm-1], axis=2)),levels=levels1,
                        colors='white',linestyles='solid',linewidths=0.3)

ax1.contour(xx1,yy1,np.transpose(np.nanmean(sstanominitextreme[:, :, mmm-1], axis=2)),levels=levels1a,
                        colors='black',linestyles='solid',linewidths=1)
ax1.contour(xx1,yy1,np.transpose(np.nanmean(sstanominitextreme[:, :, mmm-1], axis=2)),levels=levels1b,
                        colors='gray',linestyles='solid',linewidths=1)
ax1.plot(clx,cly,c='grey',linewidth=1)
ax1.set(xlim=(120.0, 290.0), ylim=(-25, 25),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('f. SLA & SSTA (InitAprOther)',loc='left',fontsize=16)
ax1.set_title('JAS',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set_xticks(np.arange(140,280.1,40));
ax1.set_xticklabels(['140 E','180','140 W','100 W'],fontsize=16);
ax1.set_yticks(np.arange(-20,20.1,10));
ax1.set_yticklabels(['20 S','10 S','Eq','10 N','20 N'],fontsize=16);
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.xaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(428)
mmm=np.arange(7,10,1)
ctrf = ax1.contourf(xx1,yy1,np.transpose(np.nanmean(slaanominitextreme[:, :, mmm-1], axis=2)),levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,np.transpose(np.nanmean(slaanominitextreme[:, :, mmm-1], axis=2)),levels=levels1,
                        colors='white',linestyles='solid',linewidths=0.3)

ax1.contour(xx1,yy1,np.transpose(np.nanmean(sstanominitextreme[:, :, mmm-1], axis=2)),levels=levels1a,
                        colors='black',linestyles='solid',linewidths=1)
ax1.contour(xx1,yy1,np.transpose(np.nanmean(sstanominitextreme[:, :, mmm-1], axis=2)),levels=levels1b,
                        colors='gray',linestyles='solid',linewidths=1)
ax1.plot(clx,cly,c='grey',linewidth=1)
ax1.set(xlim=(120.0, 290.0), ylim=(-25, 25),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('h. SLA & SSTA (InitAprOther)',loc='left',fontsize=16)
ax1.set_title('OND',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set_xticks(np.arange(140,280.1,40));
ax1.set_xticklabels(['140 E','180','140 W','100 W'],fontsize=16);
ax1.set_yticks(np.arange(-20,20.1,10));
ax1.set_yticklabels(['20 S','10 S','Eq','10 N','20 N'],fontsize=16);
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.yaxis.set_major_formatter(plt.NullFormatter())
position=fig.add_axes([0.91, 0.450, 0.011, 0.15])
cb=fig.colorbar(ctrf,cax=position,orientation='vertical',
                  ticks=np.arange(-0.2,0.21,0.1),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=16)
cb.set_label(f'SSTA (°C)', fontsize=16)
fig.savefig(r'Yourpath\Extended_Data_Fig6.pdf',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)
fig.savefig(r'Yourpath\Extended_Data_Fig6.png',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)