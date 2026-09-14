
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

mat_contents = scio.loadmat(r'Yourpath\Extended_Data_Fig8.mat')
for var_name, var_value in mat_contents.items():
    exec(f'{var_name} = var_value')

cmapcolorwithwhite=cmaps.GrayWhiteGray
newcolorwithwhite = cmapcolorwithwhite(np.linspace(0, 1, 40))
cmapcolor=cmaps.GMT_polar
newcoloraa = cmapcolor(np.linspace(0, 1, 100))
new =np. vstack((newcoloraa[15:49:1,:], newcoloraa[51:85:1,:]))
newcolor1 = ListedColormap(new)


xx1, yy1 = np.meshgrid(lon,monthplot)
xx2, yy2 = np.meshgrid(lon,lat)

levels1 = np.arange(-0.1,0.11,0.01) 
norm1= colors.Normalize(vmin=-0.1, vmax=0.1)
levels1a = np.arange(0.2,4,0.2) 
levels1b = np.arange(-4,-0.19,0.2) 

levels2 = np.arange(-0.03,0.03,0.003) 
norm2= colors.Normalize(vmin=-0.03, vmax=0.03)

levels3 = np.arange(-24,24,2) 
norm3= colors.Normalize(vmin=-24, vmax=24)



fig = plt.figure(figsize=(13.5,19.5))
fig.subplots_adjust(wspace=0.16,hspace=0.43)

ymajorLocator = MultipleLocator(2) 
ymajorFormatter = FormatStrFormatter('%1.0f')
yminorLocator = MultipleLocator(1)
xmajorLocator = MultipleLocator(20) 
xmajorFormatter = FormatStrFormatter('%1.0f')
xminorLocator = MultipleLocator(10)
ax1=fig.add_subplot(421)
ctrf = ax1.contourf(xx1,yy1,np.nanmean(zosanomEQcompelninosimilar20allmember, axis=2).T,levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,np.nanmean(zosanomEQcompelninosimilar20allmember, axis=2).T,levels=levels1,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.contour(xx1,yy1, np.nanmean(tosanomEQcompelninosimilar20allmember, axis=2).T,levels=levels1b,
                       colors='grey',linestyles='solid',linewidths=1)
ax1.contour(xx1,yy1, np.nanmean(tosanomEQcompelninosimilar20allmember, axis=2).T,levels=levels1a,
                       colors='black',linestyles='solid',linewidths=1)

ax1.set_title('a. SLA & SSTA ',loc='left',fontsize=16)
ax1.set_title('2023-like El Niños',loc='right',fontsize=16)
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
ax1.set_yticks(np.arange(2,16.1,2))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec","Feb(1)","Apr(1)"])
ax1.set(xlim=(120, 280), ylim=(1, 12)); 
ax1.xaxis.set_major_formatter(plt.NullFormatter())
ax1.axhline(y=12, c='grey', ls='--', lw=1)  
position=fig.add_axes([0.24, 0.505, 0.15, 0.010])
cb=fig.colorbar(ctrf,cax=position,orientation='horizontal',
                  ticks=np.arange(-0.1,0.11,0.1),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=16)
cb.set_label(f'SLA (m)', fontsize=16)

ax1=fig.add_subplot(422)
ctrf = ax1.contourf(xx1,yy1,np.nanmean(tauuanomEQcompelninosimilar20allmember, axis=2).T,levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,np.nanmean(tauuanomEQcompelninosimilar20allmember, axis=2).T,levels=levels2,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('b. Taux ',loc='left',fontsize=16)
ax1.set_title('2023-like El Niños',loc='right',fontsize=16)
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
ax1.set_yticks(np.arange(2,16.1,2))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec","Feb(1)","Apr(1)"])
ax1.set(xlim=(120, 280), ylim=(1, 12)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.xaxis.set_major_formatter(plt.NullFormatter())
ax1.axhline(y=12, c='grey', ls='--', lw=1)  
position=fig.add_axes([0.64, 0.505, 0.15, 0.010])
cb=fig.colorbar(ctrf,cax=position,orientation='horizontal',
                  ticks=np.arange(-0.03,0.031,0.03),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=16)
cb.set_label(f'Taux (N/m$^2$)', fontsize=16)

ax1=fig.add_subplot(423)
ctrf = ax1.contourf(xx1,yy1,np.nanmean(zosanomEQcompelninoother20allmember, axis=2).T,levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,np.nanmean(zosanomEQcompelninoother20allmember, axis=2).T,levels=levels1,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.contour(xx1,yy1, np.nanmean(tosanomEQcompelninoother20allmember, axis=2).T,levels=levels1b,
                       colors='grey',linestyles='solid',linewidths=1)
ax1.contour(xx1,yy1, np.nanmean(tosanomEQcompelninoother20allmember, axis=2).T,levels=levels1a,
                       colors='black',linestyles='solid',linewidths=1)
ax1.set_title('c. SLA & SSTA ',loc='left',fontsize=16)
ax1.set_title('Other El Niños',loc='right',fontsize=16)
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
ax1.set_yticks(np.arange(2,16.1,2))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec","Feb(1)","Apr(1)"])
ax1.set(xlim=(120, 280), ylim=(1, 12)); 
ax1.axhline(y=12, c='grey', ls='--', lw=1)  

ax1=fig.add_subplot(424)
ctrf = ax1.contourf(xx1,yy1,np.nanmean(tauuanomEQcompelninoother20allmember, axis=2).T,levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,np.nanmean(tauuanomEQcompelninoother20allmember, axis=2).T,levels=levels2,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('d. Taux ',loc='left',fontsize=16)
ax1.set_title('Other El Niños',loc='right',fontsize=16)
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
ax1.set_yticks(np.arange(2,16.1,2))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec","Feb(1)","Apr(1)"])
ax1.set(xlim=(120, 280), ylim=(1, 12)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.axhline(y=12, c='grey', ls='--', lw=1)  
yminorLocator = MultipleLocator(1)
xminorLocator = MultipleLocator(10)

ax1=fig.add_subplot(428)
ctrf = ax1.contourf(xx2,yy2,sshbuoyanom0detrend0JFMstddiffpercent.T,levels=levels3,extend='both',norm=norm3,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,sshbuoyanom0detrend0JFMstddiffpercent.T,levels=levels3,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('h. SLA s.d. change',loc='left',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.plot(clx,cly,c='grey',linewidth=1)
ax1.set_xticks(np.arange(120,291,40))
ax1.set_xticklabels(["120E","160E","160W","120W","80W"])
ax1.set_yticks(np.arange(-15,15.1,5))
ax1.set_yticklabels(["15S","10S","5S","EQ","5N","10N","15N"])
ax1.set(xlim=(120, 280));
ax1.set(ylim=(-15, 15));
ax1.axhline(y=0, c='grey', ls='--', lw=1)  
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
position=fig.add_axes([0.64, 0.09, 0.15, 0.010])
cb=fig.colorbar(ctrf,cax=position,orientation='horizontal',
                  ticks=np.arange(-24,24.1,24),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=16)
cb.set_label(f'Percentage (%)', fontsize=16)



xmajorLocator = MultipleLocator(1) 
xmajorFormatter = FormatStrFormatter('%5.0f')
xminorLocator = MultipleLocator(1)
ymajorLocator = MultipleLocator(2) 
ymajorFormatter = FormatStrFormatter('%5.0f')
yminorLocator = MultipleLocator(1)
xxx1=np.arange(1,3.1,1) 
ax1=fig.add_subplot(425)
colorlist = ['r','r','r']
ax1.bar(np.squeeze(xxx1), np.squeeze(numsimilarevents),width=0.8,color=colorlist)
ax1.errorbar(np.squeeze(xxx1), np.squeeze(numsimilarevents), np.squeeze(numsimilareventsstd),fmt='none', ecolor='k', elinewidth=4,capsize=8)
ax1.set_title('e. ',loc='left',fontsize=16)
ax1.set_title(' ',loc='right',fontsize=16)
ax1.set_ylabel('Number of similar event', fontsize=16);
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set_xticks(np.squeeze(xxx1));
ax1.set_xticklabels(['1900-1990','2000-2090','Diff'],rotation=0,fontsize=16);
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_major_formatter(ymajorFormatter)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.axhline(y=0,c='grey',lw=2)


ax1=fig.add_subplot(426)
sizes = 100  
ax1.scatter( numWPACeventchanges[2,:],numsimilarchanges[2,:], s=sizes, alpha=0.7, c='k', edgecolors='w', linewidth=0.5)
ax1.set_ylabel('Similar event number changes', fontsize=16)
ax1.set_xlabel('Strong WPAC SLA event number changes', fontsize=16)
ax1.tick_params(length=5,width=2,labelsize=16)
xmajorLocator = MultipleLocator(2) 
xmajorFormatter = FormatStrFormatter('%1.0f')
xminorLocator = MultipleLocator(1)
ymajorLocator = MultipleLocator(2) 
ymajorFormatter = FormatStrFormatter('%1.0f')
yminorLocator = MultipleLocator(1)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_major_formatter(ymajorFormatter)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_major_formatter(xmajorFormatter)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.set_title('f.(r=0.63)',loc='left',fontsize=16)
ax1.axhline(y=0, c='grey', ls='--', lw=1)  
ax1.axvline(x=0, c='grey', ls='--', lw=1)  
ax1.set(ylim=(0, 14), xlim=(0, 18.4));
slope, intercept = np.polyfit(numWPACeventchanges[2,:],np.squeeze(numsimilarchanges[2,:]),  1)
xxinterp=np.arange(0,19.0,0.1) 
fit_line = np.polyval([slope, intercept], xxinterp)
plt.plot(xxinterp, fit_line, color='red', linestyle='--', label='Linear Fit', lw=2)


xmajorLocator = MultipleLocator(1) 
xmajorFormatter = FormatStrFormatter('%5.0f')
xminorLocator = MultipleLocator(1)
ymajorLocator = MultipleLocator(1) 
ymajorFormatter = FormatStrFormatter('%5.0f')
yminorLocator = MultipleLocator(0.5)

xxx1=np.arange(1,3.1,1) 
ax1=fig.add_subplot(427)
colorlist = ['r','r','r']
ax1.bar(np.squeeze(xxx1), -np.squeeze(regressmean),width=0.8,color=colorlist)
ax1.errorbar(np.squeeze(xxx1), -np.squeeze(regressmean), np.squeeze(regressstd),fmt='none', ecolor='k', elinewidth=4,capsize=8)
ax1.set_title('g. Reg. on EQ Taux (sign reversed)',loc='left',fontsize=16)
ax1.set_title(' ',loc='right',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set_xticks(np.squeeze(xxx1));
ax1.set_xticklabels(['1900-1990','2000-2090','Diff'],rotation=0,fontsize=16);
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_major_formatter(ymajorFormatter)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.axhline(y=0,c='grey',lw=2)

fig.savefig(r'Yourpath\Extended_Data_Fig8.pdf',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)
fig.savefig(r'Yourpath\Extended_Data_Fig8.png',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)
