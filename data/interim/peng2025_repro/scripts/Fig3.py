
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
import cmaps
from matplotlib.ticker import MultipleLocator, FormatStrFormatter
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.colors as colors
from matplotlib.colors import ListedColormap
import scipy.io as scio
from cartopy.util import add_cyclic_point

mat_contents = scio.loadmat('/Users/daiyue/Documents/Maryland/data/raw/peng2025_zenodo/Fig3.mat')
for var_name, var_value in mat_contents.items():
    exec(f'{var_name} = var_value')
 
vnorm = colors.Normalize(vmin=19.0, vmax=26.0)
timemm=np.arange(1,12.1,1)
xx1, yy1 = np.meshgrid(loninterp,timemm)
xx2, yy2 = np.meshgrid(lon,lev[0:11])

cmapcolorwithwhite=cmaps.GrayWhiteGray
newcolorwithwhite = cmapcolorwithwhite(np.linspace(0, 1, 40))
cmapcolor=cmaps.GMT_polar
newcoloraa = cmapcolor(np.linspace(0, 1, 100))
new =np. vstack((newcoloraa[1:35:1,:],newcolorwithwhite[18:23,:], newcoloraa[60:95:1,:]))
newcolor1 = ListedColormap(new)

cmapcolor=cmaps.GreenMagenta16
newcoloraa = cmapcolor(np.linspace(0, 1, 100))
new =np. vstack((newcoloraa[20:40:1,:],newcolorwithwhite[19:23,:], newcoloraa[60:80:1,:]))
newcolor2 = ListedColormap(new)

levels1 = np.arange(-0.036,0.0361,0.003) 
norm1= colors.Normalize(vmin=-0.036, vmax=0.036)

levels2 = np.arange(-0.02,0.021,0.002) 
norm2= colors.Normalize(vmin=-0.02, vmax=0.02)

fig = plt.figure(figsize=(14.5,12.8))
fig.subplots_adjust(wspace=0.15,hspace=0.20)
ymajorLocator = MultipleLocator(2) 
ymajorFormatter = FormatStrFormatter('%1.0f')
yminorLocator = MultipleLocator(1)
xmajorLocator = MultipleLocator(20) 
xmajorFormatter = FormatStrFormatter('%1.0f')
xminorLocator = MultipleLocator(10)
ax1=fig.add_subplot(321)
ctrf = ax1.contourf(xx1,yy1,np.transpose(TAUXen2023anomEQ),levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,np.transpose(TAUXen2023anomEQ),levels=np.arange(-0.06,0.061,0.006),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('a. Taux',loc='left',fontsize=16)
ax1.set_title('aCTRL',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_major_formatter(ymajorFormatter)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_major_formatter(xmajorFormatter)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.set_xticks(np.arange(0,360.1,60))
ax1.set_xticklabels(["0","60E","120E","180","120W","60W","0"])
ax1.set_yticks(np.arange(2,12.1,2))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(1, 360), ylim=(1, 12)); 
ax1.xaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(322)
ctrf = ax1.contourf(xx1,yy1,np.transpose(TAUXenPACanomEQ),levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,np.transpose(TAUXenPACanomEQ),levels=np.arange(-0.06,0.061,0.006),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('b. Taux',loc='left',fontsize=16)
ax1.set_title('aPac',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_major_formatter(ymajorFormatter)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_major_formatter(xmajorFormatter)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.set_xticks(np.arange(0,360.1,60))
ax1.set_xticklabels(["0","60E","120E","180","120W","60W","0"])
ax1.set_yticks(np.arange(2,12.1,2))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(1, 360), ylim=(1, 12)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.xaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(323)
ctrf = ax1.contourf(xx1,yy1,np.transpose(TAUXenINDATLanomEQ),levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,np.transpose(TAUXenINDATLanomEQ),levels=np.arange(-0.06,0.061,0.006),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('c. Taux',loc='left',fontsize=16)
ax1.set_title('aIndAtl',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_major_formatter(ymajorFormatter)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_major_formatter(xmajorFormatter)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.set_xticks(np.arange(0,360.1,60))
ax1.set_xticklabels(["0","60E","120E","180","120W","60W","0"])
ax1.set_yticks(np.arange(2,12.1,2))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(1, 360), ylim=(1, 12)); 
ax1.xaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(324)
ctrf = ax1.contourf(xx1,yy1,np.transpose(TAUXentrendanomEQ),levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,np.transpose(TAUXentrendanomEQ),levels=np.arange(-0.06,0.061,0.006),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('d. Taux',loc='left',fontsize=16)
ax1.set_title('aTrend',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_major_formatter(xmajorFormatter)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.set_xticks(np.arange(0,360.1,60))
ax1.set_xticklabels(["0","60E","120E","180","120W","60W","0"])
ax1.set_yticks(np.arange(2,12.1,2))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(1, 360), ylim=(1, 12)); 
ax1.xaxis.set_major_formatter(plt.NullFormatter())
ax1.yaxis.set_major_formatter(plt.NullFormatter())

position=fig.add_axes([0.915, 0.55, 0.008, 0.15])
cb=fig.colorbar(ctrf,cax=position,orientation='vertical',
                  ticks=np.arange(-0.03,0.031,0.03),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=14)
cb.set_label(f'Taux (N/m$^2$)', fontsize=16)

mmm = np.arange(6, 13)
omegaen2023anomEQplot = np.transpose(np.nanmean(omegaen2023anomEQ[:, :, mmm-1], axis=2))
omegaen2023anomEQplot0=omegaen2023anomEQplot
uen2023anomEQplot = np.transpose(np.nanmean(uen2023anomEQ[:, :, mmm-1], axis=2))
speed = np.sqrt(uen2023anomEQplot**2 + (200*omegaen2023anomEQplot)**2)
uen2023anomEQplot[speed <0.1] = np.nan
omegaen2023anomEQplot[speed < 0.1] = np.nan

omegaenPACdetrend2023anomEQplot = np.transpose(np.nanmean(omegaenPACdetrend2023anomEQ[:, :, mmm-1], axis=2))
omegaenPACdetrend2023anomEQplot0=omegaenPACdetrend2023anomEQplot
uenPACdetrend2023anomEQplot = np.transpose(np.nanmean(uenPACdetrend2023anomEQ[:, :, mmm-1], axis=2))
speed = np.sqrt(uenPACdetrend2023anomEQplot**2 + (200*omegaenPACdetrend2023anomEQplot**2))
uenPACdetrend2023anomEQplot[speed < 0.1] = np.nan
omegaenPACdetrend2023anomEQplot[speed < 0.1] = np.nan


omegaenINDATLdetrend2023anomEQplot = np.transpose(np.nanmean(omegaenINDATLdetrend2023anomEQ[:, :, mmm-1], axis=2))
omegaenINDATLdetrend2023anomEQplot0=omegaenINDATLdetrend2023anomEQplot
uenINDATLdetrend2023anomEQplot = np.transpose(np.nanmean(uenINDATLdetrend2023anomEQ[:, :, mmm-1], axis=2))
speed = np.sqrt(uenINDATLdetrend2023anomEQplot**2 + (200*omegaenINDATLdetrend2023anomEQplot**2))
uenINDATLdetrend2023anomEQplot[speed <0.1] = np.nan
omegaenINDATLdetrend2023anomEQplot[speed < 0.1] = np.nan

omegaentrend2023anomEQplot = np.transpose(np.nanmean(omegaentrend2023anomEQ[:, :, mmm-1], axis=2))
omegaentrend2023anomEQplot0=omegaentrend2023anomEQplot
uentrend2023anomEQplot = np.transpose(np.nanmean(uentrend2023anomEQ[:, :, mmm-1], axis=2))
speed = np.sqrt(uentrend2023anomEQplot**2 + (200*omegaentrend2023anomEQplot**2))
uentrend2023anomEQplot[speed < 0.1] = np.nan
omegaentrend2023anomEQplot[speed < 0.1] = np.nan

ymajorLocator = MultipleLocator(100) 
ymajorFormatter = FormatStrFormatter('%1.0f')
yminorLocator = MultipleLocator(50)
xmajorLocator = MultipleLocator(20) 
xmajorFormatter = FormatStrFormatter('%1.0f')
xminorLocator = MultipleLocator(10)

ax1=fig.add_subplot(325)
ctrf = ax1.contourf(xx2,yy2,-omegaenINDATLdetrend2023anomEQplot0,levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor2)
ax1.contour(xx2,yy2,-omegaenINDATLdetrend2023anomEQplot0,levels=np.arange(-0.06,0.061,0.003),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('e. Omega & Circulation (aIndAtl)',loc='left',fontsize=16)
ax1.set_title('',loc='right',fontsize=16)
gapnum1 = 1
gapnum2 = 10
m = ax1.quiver(xx2[::gapnum1,::gapnum2],yy2[::gapnum1,::gapnum2],
                  uenINDATLdetrend2023anomEQplot[::gapnum1,::gapnum2],-200*omegaenINDATLdetrend2023anomEQplot[::gapnum1,::gapnum2],
                  zorder=2,
                  pivot='middle',
                  scale = 50,width=0.004,headwidth=3, color = 'black')
qk = ax1.quiverkey(m,0.95, 1.05,2,'2',labelpos='E',color='black',labelcolor='black',fontproperties={'size':15})
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_major_formatter(ymajorFormatter)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_major_formatter(xmajorFormatter)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.set_xticks(np.arange(0,360.1,60))
ax1.set_xticklabels(["0","60E","120E","180","120W","60W","0"])
ax1.set_yticks(np.arange(200,1000.1,200))
ax1.set(xlim=(0, 360), ylim=(1050, 50)); 

ax1=fig.add_subplot(326)
ctrf = ax1.contourf(xx2,yy2,-omegaentrend2023anomEQplot0,levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor2)
ax1.contour(xx2,yy2,-omegaentrend2023anomEQplot0,levels=np.arange(-0.06,0.061,0.003),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('f. Omega & Circulation (aTrend)',loc='left',fontsize=16)
ax1.set_title('',loc='right',fontsize=16)
gapnum1 = 1
gapnum2 = 10
m = ax1.quiver(xx2[::gapnum1,::gapnum2],yy2[::gapnum1,::gapnum2],
                  uentrend2023anomEQplot[::gapnum1,::gapnum2],-200*omegaentrend2023anomEQplot[::gapnum1,::gapnum2],
                  zorder=2,
                  pivot='middle',
                  scale = 50,width=0.004,headwidth=3, color = 'black')
qk = ax1.quiverkey(m,0.95, 1.05,2,'2',labelpos='E',color='black',labelcolor='black',fontproperties={'size':15})
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_major_formatter(ymajorFormatter)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_major_formatter(xmajorFormatter)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.set_xticks(np.arange(0,360.1,60))
ax1.set_xticklabels(["0","60E","120E","180","120W","60W","0"])
ax1.set_yticks(np.arange(200,1000.1,200))
ax1.set(xlim=(0, 360), ylim=(1050, 50)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
position=fig.add_axes([0.915, 0.15, 0.008, 0.15])
cb=fig.colorbar(ctrf,cax=position,orientation='vertical',
                  ticks=np.arange(-0.02,0.021,0.02),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=14)
cb.set_label(f'Omega (Pa/s)', fontsize=16)
fig.savefig('/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig3.png',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)
fig.savefig('/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig3.pdf',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)