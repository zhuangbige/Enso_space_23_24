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

mat_contents = scio.loadmat(r'Yourpath\Extended_Data_Fig4.mat')
for var_name, var_value in mat_contents.items():
    exec(f'{var_name} = var_value')
cmapcolorwithwhite=cmaps.GrayWhiteGray
newcolorwithwhite = cmapcolorwithwhite(np.linspace(0, 1, 40))
cmapcolor=cmaps.GMT_polar
newcoloraa = cmapcolor(np.linspace(0, 1, 100))
new =np. vstack((newcoloraa[5:46:2,:],newcolorwithwhite[18:23,:], newcoloraa[55:95:2,:]))
newcolor1 = ListedColormap(new)

xxa, yya = np.meshgrid(lon,timesince1982godas[0,0:506])
xxb, yyb = np.meshgrid(loninterp,timesince1982godas[0,0:506])
xxc, yyc = np.meshgrid(lon,timesince1982)
xx1, yy1 = np.meshgrid(loninterp,depthinterp)
xx2, yy2 = np.meshgrid(lon,depth)

levels1 = np.arange(-5.0,5.01,0.5) 
norm1= colors.Normalize(vmin=-5.0, vmax=5.0)

levels2 = np.arange(-5,5.1,0.5) 
norm2= colors.Normalize(vmin=-5, vmax=5)

levels2a = np.arange(-2.99,-0.0199,0.03) 
levels2b = np.arange(0.02,3.01,0.03) 

fig = plt.figure(figsize=(23.5,10.0))
fig.subplots_adjust(wspace=0.19,hspace=0.17)
ymajorLocator = MultipleLocator(2/12) 
ymajorFormatter = FormatStrFormatter('%1.0f')
yminorLocator = MultipleLocator(1/12)
xmajorLocator = MultipleLocator(20) 
xmajorFormatter = FormatStrFormatter('%1.0f')
xminorLocator = MultipleLocator(10)
ax1=fig.add_subplot(251)
ctrf = ax1.contourf(xxa,yya,np.transpose(oisstsince1982anomeq[:,0:506]),levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xxa,yya,np.transpose(oisstsince1982anomeq[:,0:506]),levels=levels2,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.contour(xxb,yyb, np.transpose(slasince1982anomeq),levels=levels2a,
                       colors='grey',linestyles='solid',linewidths=1)
ax1.contour(xxb,yyb, np.transpose(slasince1982anomeq),levels=levels2b,
                       colors='black',linestyles='solid',linewidths=1)
ax1.set_title('a. SSTA & SLA',loc='left',fontsize=16)
ax1.set_title('Obs',loc='right',fontsize=16)
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
ax1.set_yticks(np.arange(2023+1/12,2024.01,2/12))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(120, 280), ylim=(2023, 2024-1/12))
ax1.xaxis.set_major_formatter(plt.NullFormatter())
ax1.axhline(y=12, c='grey', ls='--', lw=1)  

ymajorLocator = MultipleLocator(2/12) 
ymajorFormatter = FormatStrFormatter('%1.0f')
yminorLocator = MultipleLocator(1/12)
xmajorLocator = MultipleLocator(20) 
xmajorFormatter = FormatStrFormatter('%1.0f')
xminorLocator = MultipleLocator(10)
ax1=fig.add_subplot(256)
ctrf = ax1.contourf(xxc,yyc,np.transpose(sstsince1982anomeqCTRL[:,:]),levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xxc,yyc,np.transpose(sstsince1982anomeqCTRL[:,:]),levels=levels2,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.contour(xxc,yyc, np.transpose(slasince1982anomeqCTRL),levels=levels2a,
                       colors='grey',linestyles='solid',linewidths=1)
ax1.contour(xxc,yyc, np.transpose(slasince1982anomeqCTRL),levels=levels2b,
                       colors='black',linestyles='solid',linewidths=1)
ax1.set_title('f. SSTA & SLA',loc='left',fontsize=16)
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
ax1.set_yticks(np.arange(2023+1/12,2024.01,2/12))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(120, 280), ylim=(2023, 2024-1/12)); 
ax1.axhline(y=12, c='grey', ls='--', lw=1)  

ymajorLocator = MultipleLocator(50) 
ymajorFormatter = FormatStrFormatter('%1.0f')
yminorLocator = MultipleLocator(10)
xmajorLocator = MultipleLocator(20) 
xmajorFormatter = FormatStrFormatter('%1.0f')
xminorLocator = MultipleLocator(10)
ax1=fig.add_subplot(252)
ctrf = ax1.contourf(xx1,yy1,tempgodasince1982eqanom2023JFM,levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,tempgodasince1982eqanom2023JFM,levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(loninterp),np.squeeze(isotherm20climeqJFM),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(loninterp),np.squeeze(isotherm20eq2023JFM),color='black',linewidth=2.5)
ax1.set_title('b. JFM Eq Temp',loc='left',fontsize=16)
ax1.set_title('Obs',loc='right',fontsize=16)
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

ax1=fig.add_subplot(253)
ctrf = ax1.contourf(xx1,yy1,tempgodasince1982eqanom2023AMJ,levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,tempgodasince1982eqanom2023AMJ,levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(loninterp),np.squeeze(isotherm20climeqAMJ),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(loninterp),np.squeeze(isotherm20eq2023AMJ),color='black',linewidth=2.5)
ax1.set_title('c. AMJ ',loc='left',fontsize=16)
ax1.set_title('Obs',loc='right',fontsize=16)
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

ax1=fig.add_subplot(254)
ctrf = ax1.contourf(xx1,yy1,tempgodasince1982eqanom2023JAS,levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,tempgodasince1982eqanom2023JAS,levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(loninterp),np.squeeze(isotherm20climeqJAS),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(loninterp),np.squeeze(isotherm20eq2023JAS),color='black',linewidth=2.5)
ax1.set_title('d. JAS ',loc='left',fontsize=16)
ax1.set_title('Obs',loc='right',fontsize=16)
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

ax1=fig.add_subplot(255)
ctrf = ax1.contourf(xx1,yy1,tempgodasince1982eqanom2023OND,levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,tempgodasince1982eqanom2023OND,levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(loninterp),np.squeeze(isotherm20climeqOND),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(loninterp),np.squeeze(isotherm20eq2023OND),color='black',linewidth=2.5)
ax1.set_title('e. OND ',loc='left',fontsize=16)
ax1.set_title('Obs',loc='right',fontsize=16)
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

ax1=fig.add_subplot(257)
ctrf = ax1.contourf(xx2,yy2,tempcombineCTRL2023anomeqJFM,levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,tempcombineCTRL2023anomeqJFM,levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqCTRLclimJFM),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqCTRL2023JFM),color='black',linewidth=2.5)
ax1.set_title('g. JFM ',loc='left',fontsize=16)
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

ax1=fig.add_subplot(258)
ctrf = ax1.contourf(xx2,yy2,tempcombineCTRL2023anomeqAMJ,levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,tempcombineCTRL2023anomeqAMJ,levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqCTRLclimAMJ),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqCTRL2023AMJ),color='black',linewidth=2.5)
ax1.set_title('h. AMJ ',loc='left',fontsize=16)
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
ax1.set(xlim=(120, 280), ylim=(250, 5)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(259)
ctrf = ax1.contourf(xx2,yy2,tempcombineCTRL2023anomeqJAS,levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,tempcombineCTRL2023anomeqJAS,levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqCTRLclimJAS),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqCTRL2023JAS),color='black',linewidth=2.5)
ax1.set_title('i. JAS ',loc='left',fontsize=16)
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
ax1.set(xlim=(120, 280), ylim=(250, 5)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(2,5,10)
ctrf = ax1.contourf(xx2,yy2,tempcombineCTRL2023anomeqOND,levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,tempcombineCTRL2023anomeqOND,levels=np.arange(-5.0,5.01,0.5),
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqCTRLclimOND),color='grey',linewidth=2.5)
ax1.plot(np.squeeze(lon),np.squeeze(isotherm20eqCTRL2023OND),color='black',linewidth=2.5)
ax1.set_title('j. OND ',loc='left',fontsize=16)
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
ax1.set(xlim=(120, 280), ylim=(250, 5)) 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
position=fig.add_axes([0.40, 0.05, 0.2, 0.012])
cb=fig.colorbar(ctrf,cax=position,orientation='horizontal',
                  ticks=np.arange(-5,5.01,2.5),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=16)
cb.set_label(f'Temp (°C)', fontsize=16)
fig.savefig(r'Yourpath\Extended_Data_Fig4.pdf',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)
fig.savefig(r'Yourpath\Extended_Data_Fig4.png',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)