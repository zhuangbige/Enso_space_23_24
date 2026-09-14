
import sys
sys.path.append(r'C:\Program Files\python')
print(sys.path)
import matplotlib
matplotlib.use('Agg')
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
from creat_mapnoproj import*
import cmaps
from matplotlib.ticker import MultipleLocator, FormatStrFormatter
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.colors as colors
from matplotlib.colors import ListedColormap
import scipy.io as scio
from cartopy.util import add_cyclic_point

mat_contents = scio.loadmat('/Users/daiyue/Documents/Maryland/data/raw/peng2025_zenodo/Fig1.mat')
for var_name, var_value in mat_contents.items():
    exec(f'{var_name} = var_value')

timemm=np.arange(1,14.1,1)
xx1, yy1 = np.meshgrid(lon,lat)
xx2, yy2 = np.meshgrid(lonplot,lat)
xx3, yy3 = np.meshgrid(loninterp,latinterp)

cmapcolorwithwhite=cmaps.GrayWhiteGray
newcolorwithwhite = cmapcolorwithwhite(np.linspace(0, 1, 40))
cmapcolor=cmaps.GMT_polar
newcoloraa = cmapcolor(np.linspace(0, 1, 100))
new =np. vstack((newcoloraa[10:40:1,:], newcoloraa[60:90:1,:]))
newcolor1 = ListedColormap(new)

levels1 = np.arange(-2.0,2.01,0.2) 
norm1= colors.Normalize(vmin=-2.0, vmax=2.0)

levels1b = np.arange(-0.24,-0.039,0.04) 
levels1a = np.arange(0.04,0.241,0.04) 

levels2 = np.arange(-240.0,240.01,20) 
norm2= colors.Normalize(vmin=-240.0, vmax=240.0)

levels3 = np.arange(-0.22,0.2201,0.02) 
norm3= colors.Normalize(vmin=-0.22, vmax=0.22)

xmajorLocator = MultipleLocator(40) 
xmajorFormatter = FormatStrFormatter('%5.0f')
xminorLocator = MultipleLocator(10)
ymajorLocator = MultipleLocator(10) 
ymajorFormatter = FormatStrFormatter('%5.1f')
yminorLocator = MultipleLocator(5)

proj = ccrs.PlateCarree(central_longitude=180)  
fig = plt.figure(figsize=(12.5,12.5))
fig.subplots_adjust(wspace=0.08,hspace=0.01)
ax1=fig.add_subplot(421)
ctrf = ax1.contourf(xx1,yy1,sstanom2023JuntoJan[:,:],levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1, sstanom2023JuntoJan[:,:],levels=np.arange(-6,6.01,0.6) ,linestyles='solid',
                        colors='white',linewidths=0.1)
ax1.axhline(y=0, c='grey', ls='--', lw=1)  
ax1.contour(xx3,yy3,sla2023JuntoJan[:,:],levels=levels1a,
                       colors='k',linestyles='solid',linewidths=1)
ax1.contour(xx3,yy3,sla2023JuntoJan[:,:],levels=levels1b,
                       colors='grey',linestyles='solid',linewidths=1)
ax1.set_title('a. SSTA & SLA (2023-24 El Niño)',loc='left',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set(ylim=(-25, 25));
ax1.set(xlim=(130, 290));
ax1.plot(clx,cly,c='grey',linewidth=1)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.set_xticks(np.arange(140,280.1,40));
ax1.set_xticklabels(['140 E','180','140 W','100 W'],fontsize=16);
ax1.set_yticks(np.arange(-20,20.1,10));
ax1.set_yticklabels(['20 S','10 S','Eq','10 N','20 N'],fontsize=16);
ax1.xaxis.set_major_formatter(plt.NullFormatter()) 

ax1=fig.add_subplot(422)
ctrf = ax1.contourf(xx1,yy1,sstanomcomparableJuntoJan[:,:],levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1, sstanomcomparableJuntoJan[:,:],levels=np.arange(-6,6.01,0.6) ,linestyles='solid',
                        colors='white',linewidths=0.1)
ax1.axhline(y=0, c='grey', ls='--', lw=1)  
ax1.contour(xx3,yy3,slacomparableJuntoJan[:,:],levels=levels1a,
                       colors='k',linestyles='solid',linewidths=1)
ax1.contour(xx3,yy3,slacomparableJuntoJan[:,:],levels=levels1b,
                       colors='grey',linestyles='solid',linewidths=1)
ax1.set_title('b. SSTA & SLA (Comparable El Niños)',loc='left',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.yaxis.set_major_formatter(plt.NullFormatter()) 
position=fig.add_axes([0.91, 0.72, 0.010, 0.12])
cb=fig.colorbar(ctrf,cax=position,orientation='vertical',
                  ticks=np.arange(-2,2.01,1),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=16)
cb.set_label(f'SSTA (°C)', fontsize=16)
ax1.set(ylim=(-25, 25));
ax1.set(xlim=(130, 290));
ax1.plot(clx,cly,c='grey',linewidth=1)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.set_xticks(np.arange(140,280.1,40));
ax1.set_xticklabels(['140 E','180','140 W','100 W'],fontsize=16);
ax1.set_yticks(np.arange(-20,20.1,10));
ax1.set_yticklabels(['20 S','10 S','Eq','10 N','20 N'],fontsize=16);
ax1.xaxis.set_major_formatter(plt.NullFormatter()) 
ax1.yaxis.set_major_formatter(plt.NullFormatter()) 

ax1=fig.add_subplot(423)
ctrf = ax1.contourf(xx1,yy1,msl2023JuntoJan[:,:],levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xx1,yy1, msl2023JuntoJan[:,:],levels=np.arange(-240,240.01,20) ,linestyles='solid',
                        colors='white',linewidths=0.1)
ax1.axhline(y=0, c='grey', ls='--', lw=1)  
gapnum1 =6
gapnum2 = 13
m = ax1.quiver(xx1[::gapnum1,::gapnum2],yy1[::gapnum1,::gapnum2],
                  uwind2023JuntoJan[::gapnum1,::gapnum2],vwind2023JuntoJan[::gapnum1,::gapnum2],
                  zorder=2,
                  pivot='middle',
                  scale = 45,width=0.006,headwidth=3, color = 'black')
qk = ax1.quiverkey(m,0.95, 1.06,2,'2',labelpos='E',color='black',labelcolor='black',fontproperties={'size':15},zorder=100)
ax1.set_title('c. MSLP & wind (2023-24 El Niño)',loc='left',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set(ylim=(-25, 25));
ax1.xaxis.set_major_formatter(plt.NullFormatter()) 
ax1.set(xlim=(130, 290));
ax1.plot(clx,cly,c='grey',linewidth=1)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.set_xticks(np.arange(140,280.1,40));
ax1.set_xticklabels(['140 E','180','140 W','100 W'],fontsize=16);
ax1.set_yticks(np.arange(-20,20.1,10));
ax1.set_yticklabels(['20 S','10 S','Eq','10 N','20 N'],fontsize=16);

ax1=fig.add_subplot(424)
ctrf = ax1.contourf(xx1,yy1,mslcomparableJuntoJan[:,:],levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xx1,yy1, mslcomparableJuntoJan[:,:],levels=np.arange(-240,240.01,20) ,linestyles='solid',
                        colors='white',linewidths=0.1)
ax1.axhline(y=0, c='grey', ls='--', lw=1)  
gapnum1 =6
gapnum2 = 13
m = ax1.quiver(xx1[::gapnum1,::gapnum2],yy1[::gapnum1,::gapnum2],
                  u10comparableJuntoJan[::gapnum1,::gapnum2],v10comparableJuntoJan[::gapnum1,::gapnum2],
                  zorder=2,
                  pivot='middle',
                  scale = 45,width=0.006,headwidth=3, color = 'black')
qk = ax1.quiverkey(m,1.01, 1.06,2,'2',labelpos='E',color='black',labelcolor='black',fontproperties={'size':15},zorder=100)

ax1.set_title('d. MSLP & wind (Comparable El Niños)',loc='left',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.yaxis.set_major_formatter(plt.NullFormatter()) 
position=fig.add_axes([0.91, 0.54, 0.010, 0.12])
cb=fig.colorbar(ctrf,cax=position,orientation='vertical',
                  ticks=np.arange(-240,240.01,120),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=16)
cb.set_label(f'MSLP (Pa)', fontsize=16)
ax1.set(ylim=(-25, 25));
ax1.xaxis.set_major_formatter(plt.NullFormatter()) 
ax1.set(xlim=(130, 290));
ax1.plot(clx,cly,c='grey',linewidth=1)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.set_xticks(np.arange(140,280.1,40));
ax1.set_xticklabels(['140 E','180','140 W','100 W'],fontsize=16);
ax1.set_yticks(np.arange(-20,20.1,10));
ax1.set_yticklabels(['20 S','10 S','Eq','10 N','20 N'],fontsize=16);
ax1.yaxis.set_major_formatter(plt.NullFormatter()) 


left, bottom, width, height = 0.13, 0.18, 0.36, 0.28
ax1 = fig.add_axes([left, bottom, width, height]) 
fig.subplots_adjust(wspace=0.13,hspace=0.32)
years = np.arange(1982, 2024)
highlight_years = [1982, 1997, 2015, 2023]
annotations = {1982: '82', 1997: '97', 2015: '15', 2023: '23'}
sizes = sstanomnino3JuntoJan*50+100  
ax1.scatter(sstanomnino3JuntoJan, uwindCWPJuntoJan, s=sizes, alpha=0.7, c='gray', edgecolors='w', linewidth=0.5)
for year in highlight_years:
    idx = np.where(years == year)  
    ax1.scatter(sstanomnino3JuntoJan[idx], uwindCWPJuntoJan[idx], s=sizes[idx], alpha=0.7, c='red', edgecolors='w', linewidth=0.5)
    ax1.text(float(np.squeeze(sstanomnino3JuntoJan[idx])), float(np.squeeze(uwindCWPJuntoJan[idx]-0.62)), annotations[year], fontsize=14, ha='center', va='bottom', color='red')
ax1.set_xlabel('Niño 3 SSTA (°C)', fontsize=16)
ax1.set_ylabel('u10 (m/s)', fontsize=16)
ax1.tick_params(length=5,width=2,labelsize=16)
xmajorLocator = MultipleLocator(1) 
xmajorFormatter = FormatStrFormatter('%1.0f')
xminorLocator = MultipleLocator(0.5)
ymajorLocator = MultipleLocator(1) 
ymajorFormatter = FormatStrFormatter('%1.0f')
yminorLocator = MultipleLocator(0.5)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_major_formatter(ymajorFormatter)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_major_formatter(xmajorFormatter)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.set_title('e.(r=0.82)',loc='left',fontsize=16)
ax1.axhline(y=0, c='grey', ls='--', lw=1)  
ax1.axvline(x=0, c='grey', ls='--', lw=1)  
ax1.set(xlim=(-2, 3.0), ylim=(-2, 3.0));
slope, intercept = np.polyfit(np.squeeze(sstanomnino3JuntoJan), uwindCWPJuntoJan, 1)
xxinterp=np.arange(-2,3.4,0.1) 
fit_line = np.polyval([slope, intercept], xxinterp)
plt.plot(xxinterp, fit_line, color='red', linestyle='--', label='Linear Fit', lw=2)


left, bottom, width, height = 0.54, 0.18, 0.36, 0.28
ax1 = fig.add_axes([left, bottom, width, height]) 
ax1.scatter(sstanomnino3JuntoJan, SOIJuntoJan, s=sizes, alpha=0.7, c='gray', edgecolors='w', linewidth=0.5)
for year in highlight_years:
    idx = np.where(years == year)  
    ax1.scatter(sstanomnino3JuntoJan[idx], SOIJuntoJan[idx], s=sizes[idx], alpha=0.7, c='red', edgecolors='w', linewidth=0.5)
    ax1.text(float(np.squeeze(sstanomnino3JuntoJan[idx])), float(np.squeeze(SOIJuntoJan[idx]-0.62)), annotations[year], fontsize=14, ha='center', va='bottom', color='red')
ax1.set_xlabel('Niño 3 SSTA (°C)', fontsize=16)
ax1.set_ylabel('SOI', fontsize=16)
ax1.tick_params(length=5,width=2,labelsize=16)
xmajorLocator = MultipleLocator(1) 
xmajorFormatter = FormatStrFormatter('%1.0f')
xminorLocator = MultipleLocator(0.5)
ymajorLocator = MultipleLocator(1) 
ymajorFormatter = FormatStrFormatter('%1.0f')
yminorLocator = MultipleLocator(0.5)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_major_formatter(ymajorFormatter)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_major_formatter(xmajorFormatter)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.set_title('f.(r=-0.82)',loc='left',fontsize=16)
ax1.axhline(y=0, c='grey', ls='--', lw=1)  
ax1.axvline(x=0, c='grey', ls='--', lw=1)  
ax1.set(xlim=(-2, 3.0), ylim=(-3, 2.0));
slope, intercept = np.polyfit(np.squeeze(sstanomnino3JuntoJan), SOIJuntoJan, 1)
xxinterp=np.arange(-2,3.4,0.1) 
fit_line = np.polyval([slope, intercept], xxinterp)
plt.plot(xxinterp, fit_line, color='red', linestyle='--', label='Linear Fit', lw=2)
# interactive display disabled for non-interactive reproduction

fig.savefig('/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig1.png',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)
fig.savefig('/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig1.pdf',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)

