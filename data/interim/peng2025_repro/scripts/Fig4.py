
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
from creat_mapnoproj import*
import cmaps
from matplotlib.ticker import MultipleLocator, FormatStrFormatter
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.colors as colors
from matplotlib.colors import ListedColormap
import scipy.io as scio
from cartopy.util import add_cyclic_point
from mpl_toolkits.basemap import Basemap

mat_contents = scio.loadmat('/Users/daiyue/Documents/Maryland/data/raw/peng2025_zenodo/Fig4.mat')
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
new =np. vstack((newcoloraa[2:42:1,:],newcolorwithwhite[18:24,:], newcoloraa[55:95:1,:]))
newcolor1 = ListedColormap(new)

sstanomnino3windextrememean[sstanomnino3windextrememean==0] = np.nan
sstanomnino3wind2023mean[sstanomnino3wind2023mean==0] = np.nan

fig = plt.figure(figsize=(15.0,18.2))
ax1=fig.add_subplot(521)
fig.subplots_adjust(wspace=0.12,hspace=0.24)
xmajorLocator = MultipleLocator(1) 
xmajorFormatter = FormatStrFormatter('%5.0f')
xminorLocator = MultipleLocator(0.5)
ymajorLocator = MultipleLocator(1) 
ymajorFormatter = FormatStrFormatter('%5.1f')
yminorLocator = MultipleLocator(0.5)  
line1 =ax1.plot(np.squeeze(timeplot),np.squeeze(sstanomnino3CTRL2023mean),color='black',linewidth=2.5, label='CTRL')
ax1.fill_between(np.squeeze(timeplot), np.squeeze(sstanomnino3CTRL2023mean)-np.squeeze(sstanomnino3CTRL2023std), np.squeeze(sstanomnino3CTRL2023mean)+np.squeeze(sstanomnino3CTRL2023std),color='black',alpha=0.3)
line1 =ax1.plot(np.squeeze(timeplot[0,3:12]),np.squeeze(sstanominitAprnino32023mean[3:12,0]),color='red',linewidth=2.5, label='InitApr2023')
ax1.fill_between(np.squeeze(timeplot[0,3:12]), np.squeeze(sstanominitAprnino32023mean[3:12,0])-np.squeeze(sstanominitAprnino32023std[3:12,0]), np.squeeze(sstanominitAprnino32023mean[3:12,0])+np.squeeze(sstanominitAprnino32023std[3:12,0]),color='red',alpha=0.3)
line1 =ax1.plot(np.squeeze(timeplot),np.squeeze(sstanomnino3wind2023mean),color='blue',linewidth=2.5, label='Wind2023')
ax1.fill_between(np.squeeze(timeplot), np.squeeze(sstanomnino3wind2023mean)-np.squeeze(sstanomnino3wind2023std), np.squeeze(sstanomnino3wind2023mean)+np.squeeze(sstanomnino3wind2023std),color='blue',alpha=0.3)
ax1.axhline(y=0, c='grey', ls='--', lw=2)   
ax1.legend(loc='upper left', frameon=True,fontsize=14) 
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.set_title('b. Niño 3 (°C)',loc='left',fontsize=16)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set_xticks(np.arange(2,14.1,2))
ax1.set_xticklabels(["Feb","Apr","Jun","Aug","Oct","Dec","Feb(1)"])
ax1.set(xlim=(1.0, 12), ylim=(-0.5, 3),
       xlabel=' ', ylabel=' ',
       title=' ');

ax1=fig.add_subplot(522) 
line1 =ax1.plot(np.squeeze(timeplot),np.squeeze(sstanomnino3CTRLextrememean),color='black',linewidth=2.5, label='CTRL')
ax1.fill_between(np.squeeze(timeplot), np.squeeze(sstanomnino3CTRLextrememean)-np.squeeze(sstanomnino3CTRLextremestd), np.squeeze(sstanomnino3CTRLextrememean)+np.squeeze(sstanomnino3CTRLextremestd),color='black',alpha=0.3)
line1 =ax1.plot(np.squeeze(timeplot[0,3:12]),np.squeeze(sstanominitAprnino3extrememean[3:12,0]),color='red',linewidth=2.5, label='InitAprOther')
ax1.fill_between(np.squeeze(timeplot[0,3:12]), np.squeeze(sstanominitAprnino3extrememean[3:12,0])-np.squeeze(sstanominitAprnino3extremestd[3:12,0]), np.squeeze(sstanominitAprnino3extrememean[3:12,0])+np.squeeze(sstanominitAprnino3extremestd[3:12,0]),color='red',alpha=0.3)
line1 =ax1.plot(np.squeeze(timeplot),np.squeeze(sstanomnino3windextrememean),color='blue',linewidth=2.5, label='WindOther')
ax1.fill_between(np.squeeze(timeplot), np.squeeze(sstanomnino3windextrememean)-np.squeeze(sstanomnino3windextremestd), np.squeeze(sstanomnino3windextrememean)+np.squeeze(sstanomnino3windextremestd),color='blue',alpha=0.3)
ax1.axhline(y=0, c='grey', ls='--', lw=2)   
ax1.legend(loc='upper left', frameon=True,fontsize=14) 
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.set_title('c. Niño 3 (°C)',loc='left',fontsize=16)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set_xticks(np.arange(2,14.1,2))
ax1.set_xticklabels(["Feb","Apr","Jun","Aug","Oct","Dec","Feb(1)"])
ax1.set(xlim=(1.0, 12), ylim=(-0.5, 3),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.yaxis.set_major_formatter(plt.NullFormatter())

xmajorLocator = MultipleLocator(20) 
xmajorFormatter = FormatStrFormatter('%5.0f')
xminorLocator = MultipleLocator(5)
ymajorLocator = MultipleLocator(10) 
ymajorFormatter = FormatStrFormatter('%5.1f')
yminorLocator = MultipleLocator(2)
proj = ccrs.PlateCarree(central_longitude=180)  
ax1=fig.add_subplot(523)
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
ax1.set_title('d. JFM SLA & SSTA',loc='left',fontsize=16)
ax1.set_title('2023/24 El Niño',loc='right',fontsize=16)
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

ax1=fig.add_subplot(524)
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
ax1.set_title('e. JFM SLA & SSTA',loc='left',fontsize=16)
ax1.set_title('Other comparable El Niños',loc='right',fontsize=16)
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

timeaa=np.arange(4,12.1,1)
timebb=np.arange(1,12.1,1)
xxc, yyc = np.meshgrid(lon,timebb)
xxd, yyd = np.meshgrid(lon,timeaa)
levels2 = np.arange(-0.2,0.21,0.02) 
levels2a = np.arange(0.4,4.1,0.4)
levels2b = np.arange(-4,-0.39,0.4)
norm2= colors.Normalize(vmin=-0.2, vmax=0.2)

ymajorLocator = MultipleLocator(2) 
ymajorFormatter = FormatStrFormatter('%1.0f')
yminorLocator = MultipleLocator(1)
xmajorLocator = MultipleLocator(20) 
xmajorFormatter = FormatStrFormatter('%1.0f')
xminorLocator = MultipleLocator(10)
ax1=fig.add_subplot(525)
ctrf = ax1.contourf(xxc,yyc,np.transpose(slaanominitApr2023eq[:,:]),levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xxc,yyc,np.transpose(slaanominitApr2023eq[:,:]),levels=levels2,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.contour(xxc,yyc, np.transpose(sstanominitApr2023eq),levels=levels2a,
                       colors='black',linestyles='solid',linewidths=1)
ax1.contour(xxc,yyc, np.transpose(sstanominitApr2023eq),levels=levels2b,
                       colors='gray',linestyles='solid',linewidths=1)
ax1.set_title('f. SLA & SSTA',loc='left',fontsize=16)
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
ax1.set_yticks(np.arange(2,12.01,2))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(120, 280), ylim=(1, 12)); 
ax1.xaxis.set_major_formatter(plt.NullFormatter())
ax1.axhline(y=4, c='grey', ls='--', lw=2)  
ax1=fig.add_subplot(526)
ctrf = ax1.contourf(xxc,yyc,np.transpose(slaanominitAprextremeeq[:,:]),levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xxc,yyc,np.transpose(slaanominitAprextremeeq[:,:]),levels=levels2,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.contour(xxc,yyc, np.transpose(sstanominitAprextremeeq),levels=levels2a,
                       colors='black',linestyles='solid',linewidths=1)
ax1.contour(xxc,yyc, np.transpose(sstanominitAprextremeeq),levels=levels2b,
                       colors='gray',linestyles='solid',linewidths=1)
ax1.set_title('g. SLA & SSTA',loc='left',fontsize=16)
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
ax1.set_yticks(np.arange(2,12.01,2))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(120, 280), ylim=(1, 12)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.xaxis.set_major_formatter(plt.NullFormatter())
ax1.axhline(y=4, c='grey', ls='--', lw=2)  

ax1=fig.add_subplot(527)
ctrf = ax1.contourf(xxd,yyd,np.transpose(slaanomwind2023eq[:,:]),levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xxd,yyd,np.transpose(slaanomwind2023eq[:,:]),levels=levels2,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.contour(xxd,yyd, np.transpose(sstanomwind2023eq),levels=levels2a,
                       colors='black',linestyles='solid',linewidths=1)
ax1.contour(xxd,yyd, np.transpose(sstanomwind2023eq),levels=levels2b,
                       colors='gray',linestyles='solid',linewidths=1)
ax1.set_title('h. SLA & SSTA',loc='left',fontsize=16)
ax1.set_title('Wind2023',loc='right',fontsize=16)
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
ax1.set_yticks(np.arange(2,12.01,2))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(120, 280), ylim=(4, 12)); 
ax1.xaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(528)
ctrf = ax1.contourf(xxd,yyd,np.transpose(slaanomwindextremeeq[:,:]),levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xxd,yyd,np.transpose(slaanomwindextremeeq[:,:]),levels=levels2,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.contour(xxd,yyd, np.transpose(sstanomwindextremeeq),levels=levels2a,
                       colors='black',linestyles='solid',linewidths=1)
ax1.contour(xxd,yyd, np.transpose(sstanomwindextremeeq),levels=levels2b,
                       colors='gray',linestyles='solid',linewidths=1)
ax1.set_title('i. SLA & SSTA',loc='left',fontsize=16)
ax1.set_title('WindOther',loc='right',fontsize=16)
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
ax1.set_yticks(np.arange(2,12.01,2))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(120, 280), ylim=(4, 12)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.xaxis.set_major_formatter(plt.NullFormatter())
position=fig.add_axes([0.92, 0.38, 0.01, 0.23])
cb=fig.colorbar(ctrf,cax=position,orientation='vertical',
                  ticks=np.arange(-0.2,0.21,0.1),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=16)
cb.set_label(f'SLA (m)', fontsize=16)

levels1 = np.arange(-0.2,0.21,0.02) 
levels1a = np.arange(0.5,5,0.5)
levels1b = np.arange(-5,-0.49,0.5)
norm1= colors.Normalize(vmin=-0.2, vmax=0.2)

xx2, yy2 = np.meshgrid(lon,depth)
levels1 = np.arange(-5.0,5.01,0.5) 
norm1= colors.Normalize(vmin=-5.0, vmax=5.0)
ymajorLocator = MultipleLocator(50) 
ymajorFormatter = FormatStrFormatter('%1.0f')
yminorLocator = MultipleLocator(10)
xmajorLocator = MultipleLocator(20) 
xmajorFormatter = FormatStrFormatter('%1.0f')
xminorLocator = MultipleLocator(10)
ax1=fig.add_subplot(529)
ctrf = ax1.contourf(xx2,yy2,tempApr2023anomeqAprtoDec,levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,tempApr2023anomeqAprtoDec,levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('j. Temp  ',loc='left',fontsize=16)
ax1.set_title('InitApr2023 (Apr-Dec)',loc='right',fontsize=16)
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
ax1.set_xlabel('Lon', fontsize=16);
ax1.set(xlim=(120, 280), ylim=(250, 5)); 
ax1=fig.add_subplot(5,2,10)
ctrf = ax1.contourf(xx2,yy2,tempextremeWindanomeqAprtoDec,levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,tempextremeWindanomeqAprtoDec,levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('k. Temp  ',loc='left',fontsize=16)
ax1.set_title('WindOther (Apr-Dec)',loc='right',fontsize=16)
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
position=fig.add_axes([0.92, 0.13, 0.01, 0.1])
cb=fig.colorbar(ctrf,cax=position,orientation='vertical',
                  ticks=np.arange(-5,5.01,5),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=16)
cb.set_label(f'Temp (°C)', fontsize=16)
ax1.set_xlabel('Lon', fontsize=16);

xmajorLocator = MultipleLocator(8) 
xmajorFormatter = FormatStrFormatter('%5.0f')
xminorLocator = MultipleLocator(1)
ymajorLocator = MultipleLocator(1) 
ymajorFormatter = FormatStrFormatter('%5.1f')
yminorLocator = MultipleLocator(0.5)
left, bottom, width, height = 0.125, 0.92, 0.775, 0.15
ax1 = fig.add_axes([left, bottom, width, height]) 
line1 =ax1.plot(np.squeeze(timesince1982),np.squeeze(sstanomnino3CTRL),color='red',linewidth=2.5, label='CTRL')
line2 =ax1.plot(np.squeeze(timesince1982),np.squeeze(oisstanomnino3[0:504]),color='black',linewidth=2.5, label='Obs')
ax1.axhline(y=0, c='grey', ls='--', lw=2)   
ax1.legend(loc='lower right', frameon=True,fontsize=16) 
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.set(xlim=(1982.0, 2024), ylim=(-3, 4),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('a. Nino 3',loc='left',fontsize=16)
ax1.set_title('r=0.90',loc='right',fontsize=16)
ax1.tick_params(length=5,width=2,labelsize=16)
fig.savefig('/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig4.pdf',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)
fig.savefig('/Users/daiyue/Documents/Maryland/data/derived/peng2025_repro/figures/Fig4.png',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)