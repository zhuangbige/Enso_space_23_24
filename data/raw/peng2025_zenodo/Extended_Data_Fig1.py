
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

mat_contents = scio.loadmat(r'Yourpath\Extended_Data_Fig1.mat')
for var_name, var_value in mat_contents.items():
    exec(f'{var_name} = var_value')    
cmapcolorwithwhite=cmaps.GrayWhiteGray
newcolorwithwhite = cmapcolorwithwhite(np.linspace(0, 1, 40))

cmapcolor=cmaps.GMT_polar
newcoloraa = cmapcolor(np.linspace(0, 1, 100))
new =np. vstack((newcoloraa[15:45:2,:],newcolorwithwhite[18:23,:], newcoloraa[55:85:2,:]))
newcolor1 = ListedColormap(new)


xx1, yy1 = np.meshgrid(lonplot,lat)
xx2, yy2 = np.meshgrid(lon,lat)

levels1 = np.arange(-3,3.01,0.3) 
norm1= colors.Normalize(vmin=-3, vmax=3)

proj = ccrs.PlateCarree(central_longitude=180)  
fig = plt.figure(figsize=(16.5,15.2))
ax1=fig.add_subplot(511, projection=proj)
ax1 = creat_map(ax1, 0, 360, -60, 60,60, 20, 10, 10, 14, 1)
ctrf = ax1.contourf(xx2,yy2,oisstanom2023FMA[:,:],levels=levels1,extend='both',norm=norm1,
                   transform=ccrs.PlateCarree(), cmap=newcolor1)
ax1.contour(xx2,yy2, oisstanom2023FMA[:,:],levels=np.arange(-3,3.01,0.6) ,linestyles='solid',
                       transform=ccrs.PlateCarree(), colors='white',linewidths=0.1)
gapnum1 =8
gapnum2 = 13
m = ax1.quiver(xx1[::gapnum1,::gapnum2],yy1[::gapnum1,::gapnum2],
                  u10anom2023FMA[::gapnum1,::gapnum2],v10anom2023FMA[::gapnum1,::gapnum2],
                  transform = ccrs.PlateCarree(),zorder=2,
                  pivot='middle',
                  scale = 70,width=0.003,headwidth=3, color = 'black')
qk = ax1.quiverkey(m,0.95, 1.05,2,'2',labelpos='E',color='black',labelcolor='black',transform = ccrs.PlateCarree(),fontproperties={'size':15})
ax1.set_title('a. SSTA & wind (FMA)',loc='left',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.xaxis.set_major_formatter(plt.NullFormatter()) 
ax1.set(ylim=(-45, 45));

ax1=fig.add_subplot(512, projection=proj)
ax1 = creat_map(ax1, 0, 360, -60, 60,60, 20, 10, 10, 14, 1)
ctrf = ax1.contourf(xx2,yy2,oisstanom2023MJJ[:,:],levels=levels1,extend='both',norm=norm1,
                   transform=ccrs.PlateCarree(), cmap=newcolor1)
ax1.contour(xx2,yy2, oisstanom2023MJJ[:,:],levels=np.arange(-3,3.01,0.6),linestyles='solid',
                       transform=ccrs.PlateCarree(), colors='white',linewidths=0.1)
gapnum1 =8
gapnum2 = 13
m = ax1.quiver(xx1[::gapnum1,::gapnum2],yy1[::gapnum1,::gapnum2],
                  u10anom2023MJJ[::gapnum1,::gapnum2],v10anom2023MJJ[::gapnum1,::gapnum2],
                  transform = ccrs.PlateCarree(),zorder=2,
                  pivot='middle',
                  scale = 70,width=0.003,headwidth=3, color = 'black')
qk = ax1.quiverkey(m,0.95, 1.05,2,'2',labelpos='E',color='black',labelcolor='black',transform = ccrs.PlateCarree(),fontproperties={'size':15})
ax1.set_title('b. MJJ',loc='left',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.xaxis.set_major_formatter(plt.NullFormatter()) 
ax1.set(ylim=(-45, 45));

ax1=fig.add_subplot(513, projection=proj)
ax1 = creat_map(ax1, 0, 360, -60, 60,60, 20, 10, 10, 14, 1)
ctrf = ax1.contourf(xx2,yy2,oisstanom2023ASO[:,:],levels=levels1,extend='both',norm=norm1,
                   transform=ccrs.PlateCarree(), cmap=newcolor1)
ax1.contour(xx2,yy2, oisstanom2023ASO[:,:],levels=np.arange(-3,3.01,0.6),linestyles='solid',
                       transform=ccrs.PlateCarree(), colors='white',linewidths=0.1)
gapnum1 =8
gapnum2 = 13
m = ax1.quiver(xx1[::gapnum1,::gapnum2],yy1[::gapnum1,::gapnum2],
                  u10anom2023ASO[::gapnum1,::gapnum2],v10anom2023ASO[::gapnum1,::gapnum2],
                  transform = ccrs.PlateCarree(),zorder=2,
                  pivot='middle',
                  scale = 70,width=0.003,headwidth=3, color = 'black')
qk = ax1.quiverkey(m,0.95, 1.05,2,'2',labelpos='E',color='black',labelcolor='black',transform = ccrs.PlateCarree(),fontproperties={'size':15})
ax1.set_title('c. ASO',loc='left',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.xaxis.set_major_formatter(plt.NullFormatter()) 
ax1.set(ylim=(-45, 45));

ax1=fig.add_subplot(514, projection=proj)
ax1 = creat_map(ax1, 0, 360, -60, 60,60, 20, 10, 10, 14, 1)
ctrf = ax1.contourf(xx2,yy2,oisstanom2023NDJ[:,:],levels=levels1,extend='both',norm=norm1,
                   transform=ccrs.PlateCarree(), cmap=newcolor1)
ax1.contour(xx2,yy2, oisstanom2023NDJ[:,:],levels=np.arange(-3,3.01,0.6),linestyles='solid',
                       transform=ccrs.PlateCarree(), colors='white',linewidths=0.1)
gapnum1 =8
gapnum2 = 13
m = ax1.quiver(xx1[::gapnum1,::gapnum2],yy1[::gapnum1,::gapnum2],
                  u10anom2023NDJ[::gapnum1,::gapnum2],v10anom2023NDJ[::gapnum1,::gapnum2],
                  transform = ccrs.PlateCarree(),zorder=2,
                  pivot='middle',
                  scale = 70,width=0.003,headwidth=3, color = 'black')
qk = ax1.quiverkey(m,0.95, 1.05,2,'2',labelpos='E',color='black',labelcolor='black',transform = ccrs.PlateCarree(),fontproperties={'size':15})
ax1.set_title('d. NDJ',loc='left',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.xaxis.set_major_formatter(plt.NullFormatter()) 
ax1.set(ylim=(-45, 45));

ax1=fig.add_subplot(515, projection=proj)
ax1 = creat_map(ax1, 0, 360, -60, 60,60, 20, 10, 10, 14, 1)
ctrf = ax1.contourf(xx2,yy2,oisstanom2024FMA[:,:],levels=levels1,extend='both',norm=norm1,
                   transform=ccrs.PlateCarree(), cmap=newcolor1)
ax1.contour(xx2,yy2, oisstanom2024FMA[:,:],levels=np.arange(-3,3.01,0.6),linestyles='solid',
                       transform=ccrs.PlateCarree(), colors='white',linewidths=0.1)
gapnum1 =8
gapnum2 = 13
m = ax1.quiver(xx1[::gapnum1,::gapnum2],yy1[::gapnum1,::gapnum2],
                  u10anom2024FMA[::gapnum1,::gapnum2],v10anom2024FMA[::gapnum1,::gapnum2],
                  transform = ccrs.PlateCarree(),zorder=2,
                  pivot='middle',
                  scale = 70,width=0.003,headwidth=3, color = 'black')
qk = ax1.quiverkey(m,0.95, 1.05,2,'2',labelpos='E',color='black',labelcolor='black',transform = ccrs.PlateCarree(),fontproperties={'size':15})
ax1.set_title('e. FMA(1)',loc='left',fontsize=16)
ax1.grid(False)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set(ylim=(-45, 45));

position=fig.add_axes([0.77, 0.43, 0.008, 0.14])
cb=fig.colorbar(ctrf,cax=position,orientation='vertical',
                  ticks=np.arange(-3,3.1,3),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=16)
cb.set_label(f'SSTA ($^\circ$C)', fontsize=16)

position=fig.add_axes([0.77, 0.43, 0.008, 0.14])
cb=fig.colorbar(ctrf,cax=position,orientation='vertical',
                  ticks=np.arange(-3,3.1,3),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=16)
cb.set_label(f'SSTA ($^\circ$C)', fontsize=16)

left, bottom, width, height = 0.282, -0.09, 0.465, 0.16
ax1 = fig.add_axes([left, bottom, width, height]) 
fig.subplots_adjust(wspace=0.19,hspace=0.25)
xmajorLocator = MultipleLocator(8) 
xmajorFormatter = FormatStrFormatter('%5.0f')
xminorLocator = MultipleLocator(1)
ymajorLocator = MultipleLocator(1) 
ymajorFormatter = FormatStrFormatter('%5.1f')
yminorLocator = MultipleLocator(0.5)
line1 =ax1.plot(np.squeeze(timesince1982),np.squeeze(heatcontentWPAC)/1e22,color='red',linewidth=2.5)
ax1.axhline(y=0, c='grey', ls='--', lw=2)   
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.set(xlim=(1982.0, 2024), ylim=(-3.5, 3.5),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('f. Heat content anom (10$^{22}$ J)',loc='left',fontsize=16)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.text(2023-3.9,2.7, r"2023", color='k', fontsize=13, ha='center', va='center')
xx=2023
yy=2.5
ax1.annotate('',
            xy=(xx, yy),  
            xytext=(xx-2.5, yy+0.2),  
            arrowprops=dict(facecolor='k', edgecolor='k', width=0.5, headwidth=4, shrink=0.05))

monthplot=np.arange(6,14.1,1)
left, bottom, width, height = 0.282, -0.30, 0.465, 0.16
ax1 = fig.add_axes([left, bottom, width, height]) 
fig.subplots_adjust(wspace=0.19,hspace=0.25)
xmajorLocator = MultipleLocator(1) 
xmajorFormatter = FormatStrFormatter('%5.0f')
xminorLocator = MultipleLocator(1)
ymajorLocator = MultipleLocator(20) 
ymajorFormatter = FormatStrFormatter('%5.1f')
yminorLocator = MultipleLocator(5)  
line1 =ax1.plot(np.squeeze(monthplot),np.squeeze(u10movingpercent[41,:])*100,color='red',linewidth=2.5, label='CWP u10')
line1 =ax1.plot(np.squeeze(monthplot),np.squeeze(mslmovingpercent[41,:])*100,color='blue',linewidth=2.5, label='SOI')
ax1.axhline(y=0, c='grey', ls='--', lw=2)   
ax1.legend(loc='upper right', frameon=True,fontsize=16) 
ax1.xaxis.set_major_locator(xmajorLocator)
ax1.xaxis.set_minor_locator(xminorLocator)
ax1.yaxis.set_major_locator(ymajorLocator)
ax1.yaxis.set_minor_locator(yminorLocator)
ax1.set(xlim=(6.0, 13), ylim=(-20, 70),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('g. ',loc='left',fontsize=16)
ax1.set_ylabel('Percentage (%)',fontsize=16)
ax1.tick_params(length=5,width=2,labelsize=16)
ax1.set_xticks(np.arange(6,13.1,1));
ax1.set_xticklabels(['JJA','JAS','ASO','SON','OND','NDJ','DJF','JFM'],fontsize=16);
plt.show()
fig.savefig(r'Yourpath\Extended_Data_Fig1.pdf',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)
fig.savefig(r'Yourpath\Extended_Data_Fig1.png',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)

