
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
mat_contents = scio.loadmat(r'Yourpath\Supplementary_Fig1.mat')
for var_name, var_value in mat_contents.items():
    exec(f'{var_name} = var_value')
cmapcolorwithwhite=cmaps.GrayWhiteGray
newcolorwithwhite = cmapcolorwithwhite(np.linspace(0, 1, 40))
cmapcolor=cmaps.GMT_polar
newcoloraa = cmapcolor(np.linspace(0, 1, 100))
new =np. vstack((newcoloraa[2:42:1,:],newcolorwithwhite[18:24,:], newcoloraa[55:95:1,:]))
newcolor1 = ListedColormap(new)

fig = plt.figure(figsize=(6.0,14.2))
fig.subplots_adjust(wspace=0.18,hspace=0.2)
ax1=fig.add_subplot(313)
xmajorLocator = MultipleLocator(2) 
xmajorFormatter = FormatStrFormatter('%5.0f')
xminorLocator = MultipleLocator(1)
ymajorLocator = MultipleLocator(0.01) 
ymajorFormatter = FormatStrFormatter('%5.1f')
yminorLocator = MultipleLocator(0.005)  
line1 =ax1.plot(np.squeeze(monthplot),np.squeeze(TAUXenPACanomCWPEQallmean),color='red',linewidth=2.5, label='aPac')
line1 =ax1.plot(np.squeeze(monthplot),np.squeeze(TAUXenINDATLanomCWPEQallmean),color='blue',linewidth=2.5, label='aIndAtl')
line1 =ax1.plot(np.squeeze(monthplot),np.squeeze(TAUXentrendanomCWPEQallmean),color='green',linewidth=2.5, label='aTrend')
ax1.axhline(y=0, c='grey', ls='--', lw=2)   
ax1.legend(loc='upper left', frameon=True,fontsize=10) 
ax1.fill_between(np.squeeze(monthplot), np.squeeze(TAUXenPACanomCWPEQallmean)-np.squeeze(TAUXenPACanomCWPEQallstd), np.squeeze(TAUXenPACanomCWPEQallmean)+np.squeeze(TAUXenPACanomCWPEQallstd),color='red',alpha=0.25)
ax1.fill_between(np.squeeze(monthplot), np.squeeze(TAUXenINDATLanomCWPEQallmean)-np.squeeze(TAUXenINDATLanomCWPEQallstd), np.squeeze(TAUXenINDATLanomCWPEQallmean)+np.squeeze(TAUXenINDATLanomCWPEQallstd),color='blue',alpha=0.25)
ax1.fill_between(np.squeeze(monthplot), np.squeeze(TAUXentrendanomCWPEQallmean)-np.squeeze(TAUXentrendanomCWPEQallstd), np.squeeze(TAUXentrendanomCWPEQallmean)+np.squeeze(TAUXentrendanomCWPEQallstd),color='green',alpha=0.25)

ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.set_title('c. Taux',loc='left',fontsize=16)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set_xticks(np.arange(2,12.0001,2))
ax1.set_xticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(1.0, 12), ylim=(-0.027, 0.045),
       xlabel=' ', ylabel=' ',
       title=' ');
xx1, yy1 = np.meshgrid(lon,monthplot1)
xx2, yy2 = np.meshgrid(loninterpCAM,monthplot2)
levels2 = np.arange(-0.032,0.0321,0.002) 
levels2a = np.arange(-0.032,0.0321,0.004) 
norm2= colors.Normalize(vmin=-0.032, vmax=0.032)
ymajorLocator = MultipleLocator(2) 
ymajorFormatter = FormatStrFormatter('%1.0f')
yminorLocator = MultipleLocator(1)
xmajorLocator = MultipleLocator(20) 
xmajorFormatter = FormatStrFormatter('%1.0f')
xminorLocator = MultipleLocator(10)
ax1=fig.add_subplot(311)
ctrf = ax1.contourf(xx1,yy1,np.transpose(tauxanomEQ2023[:,:]),levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,np.transpose(tauxanomEQ2023[:,:]),levels=levels2a,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('a. Taux ',loc='left',fontsize=16)
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
ax1.set_yticks(np.arange(2,12.0001,2))
ax1.set_yticklabels(["Feb","Apr","Jun","Aug","Oct","Dec"])
ax1.set(xlim=(120, 280), ylim=(1.0, 12)); 
ax1.xaxis.set_major_formatter(plt.NullFormatter())

ax1=fig.add_subplot(312)
ctrf = ax1.contourf(xx2,yy2,np.transpose(TAUXen2023anomEQ[:,:]),levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,np.transpose(TAUXen2023anomEQ[:,:]),levels=levels2a,
                    colors='white',linestyles='solid',linewidths=0.3)
ax1.set_title('b. Taux ',loc='left',fontsize=16)
ax1.set_title('aCTRL',loc='right',fontsize=16)
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
position=fig.add_axes([0.92, 0.56, 0.016, 0.15])
cb=fig.colorbar(ctrf,cax=position,orientation='vertical',
                  ticks=np.arange(-0.032,0.0321,0.032),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=14)
cb.set_label(f'Taux (N/m$^2$)', fontsize=14)
plt.show()
fig.savefig(r'Yourpath\Supplementary_Fig1.pdf',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)
fig.savefig(r'Yourpath\Supplementary_Fig1.png',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)


    
    

    
    