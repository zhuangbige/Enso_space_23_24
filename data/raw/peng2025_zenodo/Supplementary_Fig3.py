
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

mat_contents = scio.loadmat(r'Yourpath\Supplementary_Fig3.mat')
for var_name, var_value in mat_contents.items():
    exec(f'{var_name} = var_value')
cmapcolorwithwhite=cmaps.GrayWhiteGray
newcolorwithwhite = cmapcolorwithwhite(np.linspace(0, 1, 40))
cmapcolor=cmaps.GMT_polar
newcoloraa = cmapcolor(np.linspace(0, 1, 100))
new =np. vstack((newcoloraa[2:42:1,:],newcolorwithwhite[18:24,:], newcoloraa[55:95:1,:]))
newcolor1 = ListedColormap(new)

fig = plt.figure(figsize=(21.0,8.2))
fig.subplots_adjust(wspace=0.18,hspace=0.2)
ax1=fig.add_subplot(241)
xmajorLocator = MultipleLocator(2/12) 
xmajorFormatter = FormatStrFormatter('%5.0f')
xminorLocator = MultipleLocator(1/12)
ymajorLocator = MultipleLocator(1) 
ymajorFormatter = FormatStrFormatter('%5.1f')
yminorLocator = MultipleLocator(0.2)  
line1 =ax1.plot(np.squeeze(timesince1982),np.squeeze(nino3CTRL),color='black',linewidth=2.5, label='CTRL')
line2 =ax1.plot(np.squeeze(timesince1982[0,492:504]),np.squeeze(nino3InitApr2023[492:504,0]),color='red',linewidth=2.5, label='InitApr2023')
line3 =ax1.plot(np.squeeze(timesince1982[0,492:504]),np.squeeze(nino3InitApr2023_noHighfreq[492:504,0]),color='blue',linewidth=2.5, label='InitApr2023_noHighfreq')
ax1.axhline(y=0, c='grey', ls='--', lw=2)   
ax1.legend(loc='upper left', frameon=True,fontsize=10) 
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.set_title('a. Niño 3 (°C)',loc='left',fontsize=16)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set_xticks(np.arange(2023+1/12,2024.0001,2/12))
ax1.set_xticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(2023.0, 2024-1/12), ylim=(-0.5, 3),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.xaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(245)
xmajorLocator = MultipleLocator(2/12) 
xmajorFormatter = FormatStrFormatter('%5.0f')
xminorLocator = MultipleLocator(1/12)
ymajorLocator = MultipleLocator(1) 
ymajorFormatter = FormatStrFormatter('%5.1f')
yminorLocator = MultipleLocator(0.2)  
line1 =ax1.plot(np.squeeze(timesince1982),np.squeeze(nino3CTRLother),color='black',linewidth=2.5, label='CTRL')
line2 =ax1.plot(np.squeeze(timesince1982[0,492:504]),np.squeeze(nino3InitAprother[492:504,0]),color='red',linewidth=2.5, label='InitAprOther')
line3 =ax1.plot(np.squeeze(timesince1982[0,492:504]),np.squeeze(nino3InitAprother_noHighfreq[492:504,0]),color='blue',linewidth=2.5, label='InitAprOther_noHighfreq')
ax1.axhline(y=0, c='grey', ls='--', lw=2)   
ax1.legend(loc='upper left', frameon=True,fontsize=10) 
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.set_title('e. Niño 3 (°C)',loc='left',fontsize=16)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set_xticks(np.arange(2023+1/12,2024.0001,2/12))
ax1.set_xticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(2023.0, 2024-1/12), ylim=(-0.5, 3),
       xlabel=' ', ylabel=' ',
       title=' ');

xxc, yyc = np.meshgrid(lon,timesince1982)
levels2 = np.arange(-2.4,2.41,0.2) 
norm2= colors.Normalize(vmin=-2.4, vmax=2.4)


ymajorLocator = MultipleLocator(2/12) 
ymajorFormatter = FormatStrFormatter('%1.0f')
yminorLocator = MultipleLocator(1/12)
xmajorLocator = MultipleLocator(20) 
xmajorFormatter = FormatStrFormatter('%1.0f')
xminorLocator = MultipleLocator(10)
ax1=fig.add_subplot(242)
ctrf = ax1.contourf(xxc,yyc,np.transpose(eqsstInitApr2023[:,:]),levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xxc,yyc,np.transpose(eqsstInitApr2023[:,:]),levels=levels2,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('b. SSTA',loc='left',fontsize=16)
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
ax1.set_yticks(np.arange(2023+1/12,2024.0001,2/12))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(120, 280), ylim=(2023.0, 2024-1/12)); 
ax1.xaxis.set_major_formatter(plt.NullFormatter())
ax1.axhline(y=4, c='grey', ls='--', lw=2)  
ax1=fig.add_subplot(243)
ctrf = ax1.contourf(xxc,yyc,np.transpose(eqsstInitApr2023_noHighfreq[:,:]),levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xxc,yyc,np.transpose(eqsstInitApr2023_noHighfreq[:,:]),levels=levels2,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('c.  ',loc='left',fontsize=16)
ax1.set_title('InitApr2023_noHighfreq',loc='right',fontsize=16)
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
ax1.set_yticks(np.arange(2023+1/12,2024.0001,2/12))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(120, 280), ylim=(2023.0, 2024-1/12)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.xaxis.set_major_formatter(plt.NullFormatter())
ax1.axhline(y=4, c='grey', ls='--', lw=2) 


ax1=fig.add_subplot(244)
ctrf = ax1.contourf(xxc,yyc,np.transpose(eqsstInitApr2023_noHighfreqdiff[:,:]),levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xxc,yyc,np.transpose(eqsstInitApr2023_noHighfreqdiff[:,:]),levels=levels2,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('d.  ',loc='left',fontsize=16)
ax1.set_title('Diff',loc='right',fontsize=16)
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
ax1.set_yticks(np.arange(2023+1/12,2024.0001,2/12))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(120, 280), ylim=(2023.0, 2024-1/12)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.xaxis.set_major_formatter(plt.NullFormatter())
ax1.axhline(y=4, c='grey', ls='--', lw=2) 


ax1=fig.add_subplot(246)
ctrf = ax1.contourf(xxc,yyc,np.transpose(eqsstInitAprother[:,:]),levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xxc,yyc,np.transpose(eqsstInitAprother[:,:]),levels=levels2,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('f. SSTA',loc='left',fontsize=16)
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
ax1.set_yticks(np.arange(2023+1/12,2024.0001,2/12))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(120, 280), ylim=(2023.0, 2024-1/12)); 
ax1.axhline(y=4, c='grey', ls='--', lw=2)  

ax1=fig.add_subplot(247)
ctrf = ax1.contourf(xxc,yyc,np.transpose(eqsstInitAprother_noHighfreq[:,:]),levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xxc,yyc,np.transpose(eqsstInitAprother_noHighfreq[:,:]),levels=levels2,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('g.  ',loc='left',fontsize=16)
ax1.set_title('InitAprOther_noHighfreq',loc='right',fontsize=16)
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
ax1.set_yticks(np.arange(2023+1/12,2024.0001,2/12))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(120, 280), ylim=(2023.0, 2024-1/12)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.axhline(y=4, c='grey', ls='--', lw=2) 


ax1=fig.add_subplot(248)
ctrf = ax1.contourf(xxc,yyc,np.transpose(eqsstInitAprother_noHighfreqdiff[:,:]),levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xxc,yyc,np.transpose(eqsstInitAprother_noHighfreqdiff[:,:]),levels=levels2,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('h.  ',loc='left',fontsize=16)
ax1.set_title('Diff',loc='right',fontsize=16)
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
ax1.set_yticks(np.arange(2023+1/12,2024.0001,2/12))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(120, 280), ylim=(2023.0, 2024-1/12)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.axhline(y=4, c='grey', ls='--', lw=2) 
position=fig.add_axes([0.44, 0.06, 0.15, 0.01])
cb=fig.colorbar(ctrf,cax=position,orientation='horizontal',
                  ticks=np.arange(-2.4,2.41,1.2),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=16)
cb.set_label(f'SSTA (°C)', fontsize=16)
fig.savefig(r'Yourpath\Supplementary_Fig3.pdf',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)
fig.savefig(r'Yourpath\Supplementary_Fig3.png',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)


    
    

    
    