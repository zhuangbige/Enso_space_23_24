
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

mat_contents = scio.loadmat('/Users/daiyue/Documents/Maryland/data/raw/peng2025_zenodo/Fig2.mat')
for var_name, var_value in mat_contents.items():
    exec(f'{var_name} = var_value')
timemm=np.arange(1,19.1,1)
xx1, yy1 = np.meshgrid(lon,timemm)
xx2, yy2 = np.meshgrid(loninterp,timemm)
xx3, yy3 = np.meshgrid(loninterp,depthinterp)

cmapcolorwithwhite=cmaps.GrayWhiteGray
newcolorwithwhite = cmapcolorwithwhite(np.linspace(0, 1, 40))
cmapcolor=cmaps.GMT_polar
newcoloraa = cmapcolor(np.linspace(0, 1, 100))
new =np. vstack((newcoloraa[2:42:1,:],newcolorwithwhite[18:24,:], newcoloraa[55:95:1,:]))
newcolor1 = ListedColormap(new)

levels1 = np.arange(-0.04,0.041,0.005) 
norm1= colors.Normalize(vmin=-0.04, vmax=0.04)
levels1a = np.arange(-15,-1.0,1.5) 
levels1b = np.arange(1.5,15.01,1.5) 

levels2 = np.arange(-0.2,0.21,0.02) 
norm2= colors.Normalize(vmin=-0.2, vmax=0.2)

levels2a = np.arange(-5,-0.49,0.5) 
levels2b = np.arange(0.5,5.01,0.5) 

levels3 = np.arange(-5.0,5.01,0.5) 
norm3= colors.Normalize(vmin=-5.0, vmax=5.0)

fig = plt.figure(figsize=(13.5,18.8))
fig.subplots_adjust(wspace=0.10,hspace=0.18)
ymajorLocator = MultipleLocator(2) 
ymajorFormatter = FormatStrFormatter('%1.0f')
yminorLocator = MultipleLocator(1)
xmajorLocator = MultipleLocator(20) 
xmajorFormatter = FormatStrFormatter('%1.0f')
xminorLocator = MultipleLocator(10)
ax1=fig.add_subplot(521)
ctrf = ax1.contourf(xx1,yy1,np.transpose(tauxanomEQ2023),levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,np.transpose(tauxanomEQ2023),levels=levels1,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.contour(xx1,yy1, np.transpose(precipanomEQ2023),levels=levels1a,
                       colors='grey',linestyles='solid',linewidths=1)
ax1.contour(xx1,yy1, np.transpose(precipanomEQ2023),levels=levels1b,
                       colors='black',linestyles='solid',linewidths=1)

ax1.set_title('a. Taux & Rain',loc='left',fontsize=16)
ax1.set_title('2023/24 El Niño',loc='right',fontsize=16)
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
ax1.set_yticks(np.arange(2,17.1,2))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec","Feb(1)","Apr(1)"])
ax1.set(xlim=(120, 280), ylim=(1, 17)); 
ax1.xaxis.set_major_formatter(plt.NullFormatter())
ax1.axhline(y=12, c='grey', ls='--', lw=1)  

ax1=fig.add_subplot(522)
ctrf = ax1.contourf(xx1,yy1,np.transpose(tauxanomEQextreme),levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,np.transpose(tauxanomEQextreme),levels=levels1,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.contour(xx1,yy1, np.transpose(precipanomEQextreme),levels=levels1a,
                       colors='grey',linestyles='solid',linewidths=1)
ax1.contour(xx1,yy1, np.transpose(precipanomEQextreme),levels=levels1b,
                       colors='black',linestyles='solid',linewidths=1)

ax1.set_title('b. Taux & Rain',loc='left',fontsize=16)
ax1.set_title('Comparable El Niños',loc='right',fontsize=16)
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
ax1.set_yticks(np.arange(2,17.1,2))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec","Feb(1)","Apr(1)"])
ax1.set(xlim=(120, 280), ylim=(1, 17)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.xaxis.set_major_formatter(plt.NullFormatter())
ax1.axhline(y=12, c='grey', ls='--', lw=1)  
position=fig.add_axes([0.92, 0.77, 0.008, 0.10])
cb=fig.colorbar(ctrf,cax=position,orientation='vertical',
                  ticks=np.arange(-0.04,0.041,0.04),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=16)
cb.set_label(f'Taux (N/m$^2$)', fontsize=16)

ax1=fig.add_subplot(523)
ctrf = ax1.contourf(xx2,yy2,np.transpose(slaanomeq2023),levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,np.transpose(slaanomeq2023),levels=levels2,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.contour(xx1,yy1, np.transpose(oisstanomeq2023),levels=levels2a,
                       colors='grey',linestyles='solid',linewidths=1)
ax1.contour(xx1,yy1, np.transpose(oisstanomeq2023),levels=levels2b,
                       colors='black',linestyles='solid',linewidths=1)
ax1.set_title('c. SLA & SSTA',loc='left',fontsize=16)
ax1.set_title('2023/24 El Niño',loc='right',fontsize=16)
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
ax1.set_yticks(np.arange(2,17.1,2))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec","Feb(1)","Apr(1)"])
ax1.set(xlim=(120, 280), ylim=(1, 17)); 
ax1.xaxis.set_major_formatter(plt.NullFormatter())
ax1.axhline(y=12, c='grey', ls='--', lw=1)  

ax1=fig.add_subplot(524)
ctrf = ax1.contourf(xx2,yy2,np.transpose(slaanomeqcompextreme),levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,np.transpose(slaanomeqcompextreme),levels=levels2,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.contour(xx1,yy1, np.transpose(oisstanomeqcompextreme),levels=levels2a,
                       colors='grey',linestyles='solid',linewidths=1)
ax1.contour(xx1,yy1, np.transpose(oisstanomeqcompextreme),levels=levels2b,
                       colors='black',linestyles='solid',linewidths=1)
ax1.set_title('d. SLA & SSTA',loc='left',fontsize=16)
ax1.set_title('Comparable El Niños',loc='right',fontsize=16)
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
ax1.set_yticks(np.arange(2,17.1,2))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec","Feb(1)","Apr(1)"])
ax1.set(xlim=(120, 280), ylim=(1, 17)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.xaxis.set_major_formatter(plt.NullFormatter())
ax1.axhline(y=12, c='grey', ls='--', lw=1)  
position=fig.add_axes([0.92, 0.61, 0.008, 0.10])
cb=fig.colorbar(ctrf,cax=position,orientation='vertical',
                  ticks=np.arange(-0.2,0.21,0.2),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=16)
cb.set_label(f'SLA (m)', fontsize=16)

ymajorLocator = MultipleLocator(50) 
ymajorFormatter = FormatStrFormatter('%1.0f')
yminorLocator = MultipleLocator(10)
xmajorLocator = MultipleLocator(20) 
xmajorFormatter = FormatStrFormatter('%1.0f')
xminorLocator = MultipleLocator(10)
ax1=fig.add_subplot(525)
ctrf = ax1.contourf(xx3,yy3,np.transpose(tempeqanom2023JFM),levels=levels3,extend='both',norm=norm3,
                    cmap=newcolor1)
ax1.contour(xx3,yy3,np.transpose(tempeqanom2023JFM),levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(loninterp),np.squeeze(isotherm20climeqJFM),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(loninterp),np.squeeze(isotherm20eq2023JFM),color='black',linewidth=2.5)
ax1.set_title('e. Eq Temp (JFM)',loc='left',fontsize=16)
ax1.set_title('2023/24 El Niño',loc='right',fontsize=16)
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

ax1=fig.add_subplot(526)
ctrf = ax1.contourf(xx3,yy3,np.transpose(tempeqanomcompextremeJFM),levels=levels3,extend='both',norm=norm3,
                    cmap=newcolor1)
ax1.contour(xx3,yy3,np.transpose(tempeqanomcompextremeJFM),levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(loninterp),np.squeeze(isotherm20climeqJFM),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(loninterp),np.squeeze(isotherm20eqcompextremeJFM),color='black',linewidth=2.5)
ax1.set_title('f. Eq Temp (JFM)',loc='left',fontsize=16)
ax1.set_title('Comparable El Niños',loc='right',fontsize=16)
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
ax1.set(xlim=(120, 280), ylim=(250, 5)) 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.xaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(527)
ctrf = ax1.contourf(xx3,yy3,np.transpose(tempeqanom2023AprtoOct),levels=levels3,extend='both',norm=norm3,
                    cmap=newcolor1)
ax1.contour(xx3,yy3,np.transpose(tempeqanom2023AprtoOct),levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(loninterp),np.squeeze(isotherm20climeqAprtoOct),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(loninterp),np.squeeze(isotherm20eq2023AprtoOct),color='black',linewidth=2.5)
ax1.set_title('g. Eq Temp (Apr-Oct)',loc='left',fontsize=16)
ax1.set_title('2023/24 El Niño',loc='right',fontsize=16)
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
 
ax1=fig.add_subplot(528)
ctrf = ax1.contourf(xx3,yy3,np.transpose(tempeqanomcompextremeAprtoOct),levels=levels3,extend='both',norm=norm3,
                    cmap=newcolor1)
ax1.contour(xx3,yy3,np.transpose(tempeqanomcompextremeAprtoOct),levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(loninterp),np.squeeze(isotherm20climeqAprtoOct),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(loninterp),np.squeeze(isotherm20eqcompextremeAprtoOct),color='black',linewidth=2.5)
ax1.set_title('h. Eq Temp (Apr-Oct)',loc='left',fontsize=16)
ax1.set_title('Comparable El Niños',loc='right',fontsize=16)
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
ax1.set(xlim=(120, 280), ylim=(250, 5)) 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.xaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(529)
ctrf = ax1.contourf(xx3,yy3,np.transpose(tempeqanom2023NDJ),levels=levels3,extend='both',norm=norm3,
                    cmap=newcolor1)
ax1.contour(xx3,yy3,np.transpose(tempeqanom2023NDJ),levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(loninterp),np.squeeze(isotherm20climeqNDJ),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(loninterp),np.squeeze(isotherm20eq2023NDJ),color='black',linewidth=2.5)
ax1.set_title('i. Eq Temp (NDJ)',loc='left',fontsize=16)
ax1.set_title('2023/24 El Niño',loc='right',fontsize=16)
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

ax1=fig.add_subplot(5,2,10)
ctrf = ax1.contourf(xx3,yy3,np.transpose(tempeqanomcompextremeNDJ),levels=levels3,extend='both',norm=norm3,
                    cmap=newcolor1)
ax1.contour(xx3,yy3,np.transpose(tempeqanomcompextremeNDJ),levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(loninterp),np.squeeze(isotherm20climeqNDJ),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(loninterp),np.squeeze(isotherm20eqcompextremeNDJ),color='black',linewidth=2.5)
ax1.set_title('j. Eq Temp (NDJ)',loc='left',fontsize=16)
ax1.set_title('Comparable El Niños',loc='right',fontsize=16)
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
ax1.set(xlim=(120, 280), ylim=(250, 5)) 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
position=fig.add_axes([0.92, 0.25, 0.008, 0.199])
cb=fig.colorbar(ctrf,cax=position,orientation='vertical',
                  ticks=np.arange(-5,5.1,2.5),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=16)
cb.set_label(f'Temp (°C)', fontsize=16)
fig.savefig('/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig2.pdf',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)
fig.savefig('/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig2.png',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)
