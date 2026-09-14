
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
from scipy.stats import linregress
mat_contents = scio.loadmat(r'Yourpath\Supplementary_Fig2.mat')
for var_name, var_value in mat_contents.items():
    exec(f'{var_name} = var_value')

cmapcolorwithwhite=cmaps.GrayWhiteGray
newcolorwithwhite = cmapcolorwithwhite(np.linspace(0, 1, 40))
cmapcolor=cmaps.GMT_polar
newcoloraa = cmapcolor(np.linspace(0, 1, 100))
new =np. vstack((newcoloraa[1:41:1,:],newcolorwithwhite[18:24,:], newcoloraa[54:94:1,:]))
newcolor1 = ListedColormap(new)

slope, intercept, r_value, p_value, std_err = linregress(timesince1982, np.squeeze(oisstsince1982anomnino3relative))
trend_line = slope * timesince1982 + intercept

fig = plt.figure(figsize=(8.0,14.3))
fig.subplots_adjust(wspace=0.16,hspace=0.25)
ax1=fig.add_subplot(411)
xmajorLocator = MultipleLocator(10) 
xmajorFormatter = FormatStrFormatter('%5.0f')
xminorLocator = MultipleLocator(2)
ymajorLocator = MultipleLocator(1) 
ymajorFormatter = FormatStrFormatter('%5.1f')
yminorLocator = MultipleLocator(0.2)  
line2 =ax1.plot(np.squeeze(timesince1982),np.squeeze(oisstsince1982anomnino3relative),color='red',linewidth=2.5, label='RSST')
line3 =ax1.plot(np.squeeze(timesince1982),np.squeeze(trend_line),color='b', ls='--',linewidth=2.5, label='Trend')
ax1.axhline(y=0, c='grey', ls='--', lw=2)   
ax1.legend(loc='lower left', frameon=True,fontsize=12) 
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.set_title('a. Niño 3 RSST (°C)',loc='left',fontsize=16)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set(xlim=(1982.0, 2024-1/12), ylim=(-2.5, 3.5),
       xlabel=' ', ylabel=' ',
       title=' ');

monthplot=np.arange(1,12.0001,1)
xx2, yy2 = np.meshgrid(loninterp,monthplot)
levels2 = np.arange(-0.032,0.0321,0.002) 
norm2= colors.Normalize(vmin=-0.032, vmax=0.032)
levels2a = np.arange(-0.032,0.0321,0.004) 

ymajorLocator = MultipleLocator(2) 
ymajorFormatter = FormatStrFormatter('%1.0f')
yminorLocator = MultipleLocator(1)
xmajorLocator = MultipleLocator(20) 
xmajorFormatter = FormatStrFormatter('%1.0f')
xminorLocator = MultipleLocator(10)


ax1=fig.add_subplot(412)
ctrf = ax1.contourf(xx2,yy2,np.transpose(TAUXenPACmimusuniformwarmanomEQ[:,:]),levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,np.transpose(TAUXenPACmimusuniformwarmanomEQ[:,:]),levels=levels2a,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('b. Taux ',loc='left',fontsize=16)
ax1.set_title('aPac_RSST',loc='right',fontsize=16)
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
ax1.set_yticks(np.arange(2,12.0001,2))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(120, 280), ylim=(1.0, 12)); 
ax1.xaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(413)
ctrf = ax1.contourf(xx2,yy2,np.transpose(TAUXenPACanomEQ[:,:]),levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,np.transpose(TAUXenPACanomEQ[:,:]),levels=levels2a,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('c. Taux ',loc='left',fontsize=16)
ax1.set_title('aPac',loc='right',fontsize=16)
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
ax1.set_yticks(np.arange(2,12.0001,2))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(120, 280), ylim=(1.0, 12)); 
ax1.xaxis.set_major_formatter(plt.NullFormatter())

TAUXenPACmimusuniformwarmanomEQdiff=np.transpose(TAUXenPACmimusuniformwarmanomEQ[:,:])-np.transpose(TAUXenPACanomEQ[:,:])

ax1=fig.add_subplot(414)
ctrf = ax1.contourf(xx2,yy2,TAUXenPACmimusuniformwarmanomEQdiff,levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,TAUXenPACmimusuniformwarmanomEQdiff,levels=levels2a,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('d. Taux ',loc='left',fontsize=16)
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
ax1.set_yticks(np.arange(2,12.0001,2))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(120, 280), ylim=(1.0, 12)); 
position=fig.add_axes([0.43, 0.07, 0.2, 0.008])
cb=fig.colorbar(ctrf,cax=position,orientation='horizontal',
                  ticks=np.arange(-0.030,0.0301,0.030),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=16)
cb.set_label(f'Taux (N/m$^2$)', fontsize=16)
plt.show()
fig.savefig(r'Yourpath\Supplementary_Fig2.pdf',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)
fig.savefig(r'Yourpath\Supplementary_Fig2.png',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)
