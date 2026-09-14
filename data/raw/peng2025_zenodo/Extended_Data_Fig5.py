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

mat_contents = scio.loadmat(r'Yourpath\Extended_Data_Fig5.mat')
for var_name, var_value in mat_contents.items():
    exec(f'{var_name} = var_value')
    
vnorm = colors.Normalize(vmin=19.0, vmax=26.0)
timemm=np.arange(1,14.1,1)
xx1, yy1 = np.meshgrid(loninterp,timesince1982godas[0:506])
xx2, yy2 = np.meshgrid(lon,timesince1982godas[0:506])
xx3, yy3 = np.meshgrid(loninterp,latinterp)
xx4, yy4 = np.meshgrid(lon,lat)
cmapcolorwithwhite=cmaps.GrayWhiteGray
newcolorwithwhite = cmapcolorwithwhite(np.linspace(0, 1, 40))
cmapcolor=cmaps.GMT_polar
newcoloraa = cmapcolor(np.linspace(0, 1, 100))
new =np. vstack((newcoloraa[5:46:2,:],newcolorwithwhite[18:23,:], newcoloraa[55:95:2,:]))
newcolor1 = ListedColormap(new)

levels1 = np.arange(-0.2,0.21,0.02) 
norm1= colors.Normalize(vmin=-0.2, vmax=0.2)
levels1a = np.arange(0.4,4.01,0.4) 
levels1b = np.arange(-4,-0.399,0.4) 

levels11 = np.arange(-2,2.01,0.4) 
norm11= colors.Normalize(vmin=-2, vmax=2)

levels2 = np.arange(-4,4.1,0.4) 
norm2= colors.Normalize(vmin=-4, vmax=4)

def smooth2D(A, kernel_size, kernel_type):
    if kernel_type == 'box':
        kernel = np.ones((kernel_size, kernel_size)) / (kernel_size ** 2)
    elif kernel_type == 'gaussian':
        kernel = gaussian_kernel(kernel_size)
    elif kernel_type == 'edge_detect':
        kernel = edge_detection_kernel()
    else:
        raise ValueError("Invalid kernel type.")        
    return convolve2d(A, kernel, mode='same', boundary='symm')

oisstsince1982anom2020JDplot2 = smooth2D(oisstsince1982anom2020JDplot,3,'box') 
oisstsince1982anom2021JDplot2 = smooth2D(oisstsince1982anom2021JDplot,3,'box') 
oisstsince1982anom2022JDplot2 = smooth2D(oisstsince1982anom2022JDplot,3,'box') 

oisstsince1982anom20231to3plot2 = smooth2D(oisstsince1982anom20231to3plot,3,'box') 
oisstsince1982anom20234to6plot2 = smooth2D(oisstsince1982anom20234to6plot,3,'box') 
oisstsince1982anom20237to9plot2 = smooth2D(oisstsince1982anom20237to9plot,3,'box') 

fig = plt.figure(figsize=(20.5,13.8))
fig.subplots_adjust(wspace=0.16,hspace=0.21)
ymajorLocator = MultipleLocator(6/12) 
ymajorFormatter = FormatStrFormatter('%1.0f')
yminorLocator = MultipleLocator(1/12)
xmajorLocator = MultipleLocator(20) 
xmajorFormatter = FormatStrFormatter('%1.0f')
xminorLocator = MultipleLocator(10)

ax1=fig.add_subplot(331)
ctrf = ax1.contourf(xx1,yy1,np.transpose(slasince1982anomeq[:,0:506]),levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx1,yy1,np.transpose(slasince1982anomeq[:,0:506]),levels=np.arange(-0.2,0.21,0.04),
                    colors='white',linestyles='solid',linewidths=0.1)
ax1.set_title('a. SLA',loc='left',fontsize=16)
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
ax1.set_yticks(np.arange(2020,2024.1,6/12))
ax1.set_yticklabels(["2020","Jun","2021","Jun","2022","Jun","2023","Jun","2024"])
ax1.set(xlim=(120, 280), ylim=(2020, 2024-1/12)); 
ax1.axhline(y=2023, c='grey', ls='--', lw=1)   
position=fig.add_axes([0.363, 0.70, 0.008, 0.15])
cb=fig.colorbar(ctrf,cax=position,orientation='vertical',
                  ticks=np.arange(-0.2,0.21,0.2),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=13)

ax1=fig.add_subplot(332)
ctrf = ax1.contourf(xx2,yy2,np.transpose(oisstsince1982anomeq[:,0:506]),levels=levels11,extend='both',norm=norm11,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,np.transpose(oisstsince1982anomeq[:,0:506]),levels=np.arange(-4,4.01,0.8),
                    colors='white',linestyles='solid',linewidths=0.1)
ax1.set_title('b. SSTA',loc='left',fontsize=16)
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
ax1.set_yticks(np.arange(2020,2024.1,6/12))
ax1.set_yticklabels(["2020","Jun","2021","Jun","2022","Jun","2023","Jun","2024"])
ax1.set(xlim=(120, 280), ylim=(2020, 2024-1/12)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.axhline(y=2023, c='grey', ls='--', lw=1)  
position=fig.add_axes([0.635, 0.70, 0.008, 0.15])
cb=fig.colorbar(ctrf,cax=position,orientation='vertical',
                  ticks=np.arange(-2,2.01,2),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=14)

ax1=fig.add_subplot(333)
ctrf = ax1.contourf(xx2,yy2,np.transpose(u10since1982combineanomEQ[:,0:506]),levels=levels2,extend='both',norm=norm2,
                    cmap=newcolor1)
ax1.contour(xx2,yy2,np.transpose(u10since1982combineanomEQ[:,0:506]),levels= np.arange(-4,4.1,0.8),
                    colors='white',linestyles='solid',linewidths=0.1)
ax1.set_title('c. u10 anom',loc='left',fontsize=16)
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
ax1.set_yticks(np.arange(2020,2024.1,6/12))
ax1.set_yticklabels(["2020","Jun","2021","Jun","2022","Jun","2023","Jun","2024"])
ax1.set(xlim=(120, 280), ylim=(2020, 2024-1/12)); 
ax1.yaxis.set_major_formatter(plt.NullFormatter())
ax1.axhline(y=2023, c='grey', ls='--', lw=1)   
position=fig.add_axes([0.91, 0.700, 0.008, 0.15])
cb=fig.colorbar(ctrf,cax=position,orientation='vertical',
                  ticks=np.arange(-4,4.01,2),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=16)
cb.set_label(f'u10 (m/s)', fontsize=16)

xmajorLocator = MultipleLocator(20) 
xmajorFormatter = FormatStrFormatter('%5.0f')
xminorLocator = MultipleLocator(5)
ymajorLocator = MultipleLocator(10) 
ymajorFormatter = FormatStrFormatter('%5.1f')
yminorLocator = MultipleLocator(2)
proj = ccrs.PlateCarree(central_longitude=180)  
# fig = plt.figure(figsize=(19,4.5))
ax1=fig.add_subplot(334)
ctrf = ax1.contourf(xx3,yy3,slasince1982anom2020JDplot[:,:],levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx3,yy3, slasince1982anom2020JDplot[:,:],levels=np.arange(-0.4,0.41,0.04),
                        colors='white',linestyles='solid',linewidths=0.1)
ax1.contour(xx4,yy4, oisstsince1982anom2020JDplot2[:,:],levels=levels1a,
                        colors='magenta',linestyles='solid',linewidths=1.5)
ax1.contour(xx4,yy4, oisstsince1982anom2020JDplot2[:,:],levels=levels1b,
                        colors='magenta',linestyles='dashed',linewidths=1.5)
gapnum1 = 5
gapnum2 = 10
m = ax1.quiver(xx4[::gapnum1,::gapnum2],yy4[::gapnum1,::gapnum2],
                  u10since1982combineanom2020JDplot[::gapnum1,::gapnum2],v10since1982combineanom2020JDplot[::gapnum1,::gapnum2],
                  zorder=2,
                  pivot='middle',
                  scale = 25,width=0.004,headwidth=3, color = 'black')
qk = ax1.quiverkey(m,0.99, 1.05,1,'1',labelpos='E',color='black',labelcolor='black',fontproperties={'size':15})
ax1.plot(clx,cly,c='grey',linewidth=1)
ax1.set(xlim=(120.0, 290.0), ylim=(-20, 20),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('d. SLA, SSTA & Wind (Jun-Dec 2020)',loc='left',fontsize=15)
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

ax1=fig.add_subplot(335)
ctrf = ax1.contourf(xx3,yy3,slasince1982anom2021JDplot[:,:],levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx3,yy3, slasince1982anom2021JDplot[:,:],levels=np.arange(-0.4,0.41,0.04),
                        colors='white',linestyles='solid',linewidths=0.1)
ax1.contour(xx4,yy4, oisstsince1982anom2021JDplot2[:,:],levels=levels1a,
                        colors='magenta',linestyles='solid',linewidths=1.5)
ax1.contour(xx4,yy4, oisstsince1982anom2021JDplot2[:,:],levels=levels1b,
                        colors='magenta',linestyles='dashed',linewidths=1.5)
gapnum1 = 5
gapnum2 = 10
m = ax1.quiver(xx4[::gapnum1,::gapnum2],yy4[::gapnum1,::gapnum2],
                  u10since1982combineanom2021JDplot[::gapnum1,::gapnum2],v10since1982combineanom2021JDplot[::gapnum1,::gapnum2],
                  zorder=2,
                  pivot='middle',
                  scale = 25,width=0.004,headwidth=3, color = 'black')
qk = ax1.quiverkey(m,0.95, 1.05,1,'1',labelpos='E',color='black',labelcolor='black',fontproperties={'size':15})
ax1.plot(clx,cly,c='grey',linewidth=1)
ax1.set(xlim=(120.0, 290.0), ylim=(-20, 20),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('e. Jun-Dec 2021',loc='left',fontsize=16)
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


ax1=fig.add_subplot(336)
ctrf = ax1.contourf(xx3,yy3,slasince1982anom2022JDplot[:,:],levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx3,yy3, slasince1982anom2022JDplot[:,:],levels=np.arange(-0.4,0.41,0.04),
                        colors='white',linestyles='solid',linewidths=0.1)
ax1.contour(xx4,yy4, oisstsince1982anom2022JDplot2[:,:],levels=levels1a,
                        colors='magenta',linestyles='solid',linewidths=1.5)
ax1.contour(xx4,yy4, oisstsince1982anom2022JDplot2[:,:],levels=levels1b,
                        colors='magenta',linestyles='dashed',linewidths=1.5)
gapnum1 = 5
gapnum2 = 10
m = ax1.quiver(xx4[::gapnum1,::gapnum2],yy4[::gapnum1,::gapnum2],
                  u10since1982combineanom2022JDplot[::gapnum1,::gapnum2],v10since1982combineanom2022JDplot[::gapnum1,::gapnum2],
                  zorder=2,
                  pivot='middle',
                  scale = 25,width=0.004,headwidth=3, color = 'black')
qk = ax1.quiverkey(m,0.95, 1.05,1,'1',labelpos='E',color='black',labelcolor='black',fontproperties={'size':15})
ax1.plot(clx,cly,c='grey',linewidth=1)
ax1.set(xlim=(120.0, 290.0), ylim=(-20, 20),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('f. Jun-Dec 2022',loc='left',fontsize=16)
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


ax1=fig.add_subplot(337)
ctrf = ax1.contourf(xx3,yy3,slasince1982anom20231to3plot[:,:],levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx3,yy3, slasince1982anom20231to3plot[:,:],levels=np.arange(-0.4,0.41,0.04),
                        colors='white',linestyles='solid',linewidths=0.1)
ax1.contour(xx4,yy4, oisstsince1982anom20231to3plot2[:,:],levels=levels1a,
                        colors='magenta',linestyles='solid',linewidths=1.5)
ax1.contour(xx4,yy4, oisstsince1982anom20231to3plot2[:,:],levels=levels1b,
                        colors='magenta',linestyles='dashed',linewidths=1.5)
gapnum1 = 5
gapnum2 = 10
m = ax1.quiver(xx4[::gapnum1,::gapnum2],yy4[::gapnum1,::gapnum2],
                  u10since1982combineanom20231to3plot[::gapnum1,::gapnum2],v10since1982combineanom20231to3plot[::gapnum1,::gapnum2],
                  zorder=2,
                  pivot='middle',
                  scale = 25,width=0.004,headwidth=3, color = 'black')
qk = ax1.quiverkey(m,0.95, 1.05,1,'1',labelpos='E',color='black',labelcolor='black',fontproperties={'size':15})
ax1.plot(clx,cly,c='grey',linewidth=1)
ax1.set(xlim=(120.0, 290.0), ylim=(-20, 20),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('g. JFM 2023',loc='left',fontsize=16)
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

ax1=fig.add_subplot(338)
ctrf = ax1.contourf(xx3,yy3,slasince1982anom20234to6plot[:,:],levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx3,yy3, slasince1982anom20234to6plot[:,:],levels=np.arange(-0.4,0.41,0.04),
                        colors='white',linestyles='solid',linewidths=0.1)
ax1.contour(xx4,yy4, oisstsince1982anom20234to6plot2[:,:],levels=levels1a,
                        colors='magenta',linestyles='solid',linewidths=1.5)
ax1.contour(xx4,yy4, oisstsince1982anom20234to6plot2[:,:],levels=levels1b,
                        colors='magenta',linestyles='dashed',linewidths=1.5)
gapnum1 = 5
gapnum2 = 10
m = ax1.quiver(xx4[::gapnum1,::gapnum2],yy4[::gapnum1,::gapnum2],
                  u10since1982combineanom20234to6plot[::gapnum1,::gapnum2],v10since1982combineanom20234to6plot[::gapnum1,::gapnum2],
                  zorder=2,
                  pivot='middle',
                  scale = 25,width=0.004,headwidth=3, color = 'black')
qk = ax1.quiverkey(m,0.95, 1.05,1,'1',labelpos='E',color='black',labelcolor='black',fontproperties={'size':15})
ax1.plot(clx,cly,c='grey',linewidth=1)
ax1.set(xlim=(120.0, 290.0), ylim=(-20, 20),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('h. AMJ 2023',loc='left',fontsize=16)
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

ax1=fig.add_subplot(339)
ctrf = ax1.contourf(xx3,yy3,slasince1982anom20237to9plot[:,:],levels=levels1,extend='both',norm=norm1,
                    cmap=newcolor1)
ax1.contour(xx3,yy3, slasince1982anom20237to9plot[:,:],levels=np.arange(-0.4,0.41,0.04),
                        colors='white',linestyles='solid',linewidths=0.1)
ax1.contour(xx4,yy4, oisstsince1982anom20237to9plot2[:,:],levels=levels1a,
                        colors='magenta',linestyles='solid',linewidths=1.5)
ax1.contour(xx4,yy4, oisstsince1982anom20237to9plot2[:,:],levels=levels1b,
                        colors='magenta',linestyles='dashed',linewidths=1.5)
gapnum1 = 5
gapnum2 = 10
m = ax1.quiver(xx4[::gapnum1,::gapnum2],yy4[::gapnum1,::gapnum2],
                  u10since1982combineanom20237to9plot[::gapnum1,::gapnum2],v10since1982combineanom20237to9plot[::gapnum1,::gapnum2],
                  zorder=2,
                  pivot='middle',
                  scale = 25,width=0.004,headwidth=3, color = 'black')
qk = ax1.quiverkey(m,0.95, 1.05,1,'1',labelpos='E',color='black',labelcolor='black',fontproperties={'size':15})
ax1.plot(clx,cly,c='grey',linewidth=1)
ax1.set(xlim=(120.0, 290.0), ylim=(-20, 20),
       xlabel=' ', ylabel=' ',
       title=' ');
ax1.set_title('i. JAS 2023',loc='left',fontsize=16)
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
position=fig.add_axes([0.91, 0.300, 0.008, 0.15])
cb=fig.colorbar(ctrf,cax=position,orientation='vertical',
                  ticks=np.arange(-0.2,0.21,0.2),fraction=.5,extend='both')
cb.ax.tick_params(labelsize=16)
cb.set_label(f'SLA (m)', fontsize=16)
fig.savefig(r'Yourpath\Extended_Data_Fig5.pdf',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)
fig.savefig(r'Yourpath\Extended_Data_Fig5.png',dpi=500, bbox_inches = 'tight', pad_inches = 0.03)
