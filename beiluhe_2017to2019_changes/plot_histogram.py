#!/usr/bin/env python
# Filename: plot_histogram.py 
"""
introduction: plot histogram

authors: Huang Lingcao
email:huanglingcao@gmail.com
add time: 23 February, 2019
"""

import os, sys
HOME = os.path.expanduser('~')
# path of DeeplabforRS
codes_dir2 =  HOME +'/codes/PycharmProjects/DeeplabforRS'
sys.path.insert(0, codes_dir2)


import basic_src.io_function as io_function
import basic_src.basic as basic

import rasterio
import numpy as np

import matplotlib
from matplotlib.ticker import FuncFormatter
import matplotlib.pyplot as plt


from vector_features import read_attribute

def read_oneband_image_to_1dArray(image_path,nodata=None, ignore_small=None):

    if os.path.isfile(image_path) is False:
        raise IOError("error, file not exist: " + image_path)

    with rasterio.open(image_path) as img_obj:
        # read the all bands (only have one band)
        indexes = img_obj.indexes
        if len(indexes) != 1:
            raise IOError('error, only support one band')

        data = img_obj.read(indexes)
        data_1d = data.flatten()  # convert to one 1d, row first.

        if nodata is not None:
            data_1d = data_1d[data_1d != nodata]
        if ignore_small is not None:
            data_1d = data_1d[data_1d >= ignore_small ]

        return data_1d

global_bin_size = 50   # remember to change this one
def to_percent(y, position):
    # Ignore the passed in position. This has the effect of scaling the default
    # tick locations.

    # print(global_bin_size)
    # s = str(100 * y*bin_size)
    s = "%.0f"%(100 * y*global_bin_size)

    # The percent symbol needs escaping in latex
    # if matplotlib.rcParams['text.usetex'] is True:
    #     return s + r'$\%$'
    # else:
    #     return s + '%'
    if matplotlib.rcParams['text.usetex'] is True:
        return s
    else:
        return s

def histogram2logfile(value_list,bins,hist_tag=None):
    if hist_tag is not None:
        basic.outputlogMessage('the following is the histogram information of %s'%hist_tag)
    # output hist, min, max, average, accumulate percentage
    np_hist,bin_edges = np.histogram(value_list, bins=bins)
    basic.outputlogMessage("np_hist: " + str(np_hist))
    basic.outputlogMessage("min value: " + str(min(value_list)))
    basic.outputlogMessage("max value: " + str(max(value_list)))
    basic.outputlogMessage("average value: " + str(sum(value_list)/float(len(value_list))))
    if len(value_list) != np.sum(np_hist):
        basic.outputlogMessage('warning: the count (%d) of input is not equal to the count (%d)'
                               ' in histogram'%(len(value_list),int(np.sum(np_hist))))
    acc_per = np.cumsum(np_hist)/np.sum(np_hist)
    basic.outputlogMessage("accumulate percentage: " + str(acc_per))


def draw_two_list_histogram(shp_file,field_name,ano_list,output,bins=None,labels=None,color=None,hatch="",ylim=None):
    """

    Args:
        shp_file:  shape file path
        attribute_name: name of attribute
        output: output the figure

    Returns: True if successful, False otherwise

    """
    values = read_attribute(shp_file,field_name)

    x_multi = [values,ano_list]
    fig, ax = plt.subplots(nrows=1, ncols=1,figsize=(8,6))
    # fig_obj = plt.figure(figsize=(8,6))  # create a new figure
    # ax = Subplot(fig_obj, 111)
    # fig_obj.add_subplot(ax)

    # density=True,
    # bins = "auto"
    # n_bins = 10
    # bins = np.arange(4400,5000,50)
    n, bins, patches = ax.hist(x_multi,bins=bins,density = True, alpha=0.75, ec="black",linewidth='1.5',
                               color=color,hatch=hatch,label=labels,rwidth=1)

    # n, bins, patches = ax.hist(values,bins=bins,normed = True, alpha=0.75, ec="black",linewidth='1.5',
    #                            color=['grey'],hatch=hatch,label=['RTS'],stacked=True)
    fontsize=18
    ax.legend(prop={'size': fontsize})

    # Create the formatter using the function to_percent. This multiplies all the
    # default labels by 100, making them all percentages
    formatter = FuncFormatter(to_percent)

    # Set the formatter
    plt.gca().yaxis.set_major_formatter(formatter)



    # hide the right and top boxed axis
    # ax.axis["right"].set_visible(False)
    # ax.axis["top"].set_visible(False)

    plt.xticks(bins)
    # ax1.get_xaxis().set_ticklabels(layer_num)

    # plt.tick_params(direction='out', length=6, width=2)
    # ax.tick_params(axis='both',direction='out', colors='red',length=0.1)
    ax.tick_params(axis='both',which='both',direction='out', length=7,labelsize=fontsize) #,width=50 #,

    if 'dem' in field_name or 'pisr' in field_name or 'asp' in field_name \
            or 'tpi' in field_name or 'slo' in field_name:
        ax.tick_params(axis='x',labelrotation=90)

    if ylim is not None:
        ax.set_ylim(ylim)

    plt.gcf().subplots_adjust(bottom=0.15)
    # plt.grid(True)
    plt.savefig(output)
    basic.outputlogMessage("Output figures to %s"%os.path.abspath(output))
    basic.outputlogMessage("ncount: " + str(n))
    basic.outputlogMessage("bins: "+ str(bins))
    histogram2logfile(values, bins,hist_tag=labels[0])
    histogram2logfile(ano_list, bins, hist_tag=labels[1])
    # plt.show()

def draw_one_list_histogram(value_list,output,bins=None,labels=None,color=None,hatch="",xlabelrotation=None,ylim=None):


    fig, ax = plt.subplots(nrows=1, ncols=1,figsize=(8,8))
    n, bins, patches = ax.hist(value_list,bins=bins, alpha=0.75, ec="black",linewidth='1.5',
                               color=color,hatch=hatch,label=labels,rwidth=1) #density = True,

    # ax.legend(prop={'size': 12})
    plt.xticks(bins)
    ax.tick_params(axis='both',which='both',direction='out',length=7,labelsize=20) #,width=50 #,
    if xlabelrotation is not None:
        ax.tick_params(axis='x', labelrotation=90)

    if ylim is not None:
        ax.set_ylim(ylim)

    plt.gcf().subplots_adjust(bottom=0.15)
    # plt.grid(True)
    plt.savefig(output)  #
    basic.outputlogMessage("Output figures to %s"%os.path.abspath(output))
    basic.outputlogMessage("ncount: " + str(n))
    basic.outputlogMessage("bins: "+ str(bins))
    histogram2logfile(value_list, bins)
    # plt.show()

def draw_two_values_hist(shp_file,field_name,raster_file,output,logfile,bin_min,bin_max,bin_width,labels,ylim):

    raster_values = read_oneband_image_to_1dArray(raster_file, nodata=0, ignore_small=bin_min)
    bins = np.arange(bin_min, bin_max, bin_width)

    # update
    global global_bin_size
    global_bin_size = bin_width
    ylim = [ item/(100.0*bin_width) for item in ylim]

    draw_two_list_histogram(shp_file, field_name, raster_values, output, bins=bins,labels=labels,
                            color=['black', 'silver'],ylim=ylim)
    io_function.move_file_to_dst('processLog.txt', os.path.join(out_dir,logfile), overwrite=True)
    io_function.move_file_to_dst(output, os.path.join(out_dir,output), overwrite=True)


def draw_one_value_hist(shp_file,field_name,output,logfile,bin_min,bin_max,bin_width,ylim):

    values = read_attribute(shp_file, field_name)
    if field_name == 'INarea':                      # m^2 to ha
        values = [item/10000.0 for item in values]

    xlabelrotation = None
    if 'area' in field_name or 'INperimete' in field_name or 'circularit' in field_name or 'aspectLine' in field_name or \
        'dem' in field_name or 'slo_max' in field_name:
        xlabelrotation = 90

    bins = np.arange(bin_min, bin_max, bin_width)

    # plot histogram of slope values
    # value_list,output,bins=None,labels=None,color=None,hatch=""
    draw_one_list_histogram(values, output,bins=bins,color=['grey'],xlabelrotation=xlabelrotation,ylim=ylim )  # ,hatch='-'
    io_function.move_file_to_dst('processLog.txt', os.path.join(out_dir, logfile), overwrite=True)
    io_function.move_file_to_dst(output, os.path.join(out_dir, output), overwrite=True)


def draw_three_hist(shp_2017,shp_2018,shp_2019, field_name, out_pre_name, bin_min,bin_max,bin_width,ylim):

    draw_one_value_hist(shp_2017,field_name,out_pre_name+'_201707.jpg',out_pre_name+'_201707.txt',bin_min,bin_max,bin_width,ylim)
    draw_one_value_hist(shp_2018,field_name,out_pre_name+'_201807.jpg',out_pre_name+'_201807.txt',bin_min,bin_max,bin_width,ylim)
    draw_one_value_hist(shp_2019,field_name,out_pre_name+'_201907.jpg',out_pre_name+'_201907.txt',bin_min,bin_max,bin_width,ylim)



if __name__ == "__main__":



    # dem=HOME+'/Data/Qinghai-Tibet/beiluhe/DEM/srtm_30/beiluhe_srtm30_utm_basinExt.tif'
    # slope=HOME+'/Data/Qinghai-Tibet/beiluhe/DEM/srtm_30/beiluhe_srtm30_utm_basinExt_slope.tif'
    # aspect=HOME+'/Data/Qinghai-Tibet/beiluhe/DEM/srtm_30/beiluhe_srtm30_utm_basinExt_apect.tif'
    # pisr = HOME+'/Data/Qinghai-Tibet/beiluhe/DEM/srtm_30/dem_derived/beiluhe_srtm30_utm_basinExt_PISR_total_perDay.tif'
    # tpi = HOME+'/Data/Qinghai-Tibet/beiluhe/DEM/srtm_30/dem_derived/beiluhe_srtm30_utm_basinExt_tpi.tif'

    ##########################################################################################
    # plot histogram on the ground truth
    out_dir=HOME+'/Data/Qinghai-Tibet/beiluhe/result/result_multi_temporal_changes_17-19July/BLH_2017To2019_manual_delineation'

    shp_dir = os.path.expanduser('~/Data/Qinghai-Tibet/beiluhe/thaw_slumps')
    ground_truth_201707 = os.path.join(shp_dir, 'train_polygons_for_planet_201707/blh_manu_RTS_utm_201707.shp')
    ground_truth_201807 = os.path.join(shp_dir, 'train_polygons_for_planet_201807/blh_manu_RTS_utm_201807.shp')
    ground_truth_201907 = os.path.join(shp_dir, 'train_polygons_for_planet_201907/blh_manu_RTS_utm_201907.shp')

    # INarea, y lim: we want,[0,160]
    # draw_three_hist(ground_truth_201707, ground_truth_201807, ground_truth_201907,'INarea','area_GT',0,31,2,[0,160])

    # perimeter
    # draw_three_hist(ground_truth_201707, ground_truth_201807, ground_truth_201907,'INperimete','perimeter_GT',200,6500,500,[0,150])

    # dem_mean, y lim:
    # draw_three_hist(ground_truth_201707, ground_truth_201807, ground_truth_201907,'dem_mean','dem_mean_GT',4500,5000,25,[0,75])

    # dem_std, y lim:
    # draw_three_hist(ground_truth_201707, ground_truth_201807, ground_truth_201907,'dem_std','dem_std_GT',0,26,1.5,[0,50])

    # slo_mean
    # draw_three_hist(ground_truth_201707, ground_truth_201807, ground_truth_201907,'slo_mean','slope_mean_GT',2,15,1,[0,70])
    # slo_min
    # draw_three_hist(ground_truth_201707, ground_truth_201807, ground_truth_201907,'slo_min','slope_min_GT',0,12,1,[0,100])
    # slo_max
    # draw_three_hist(ground_truth_201707, ground_truth_201807, ground_truth_201907,'slo_max','slope_max_GT',3,22,1,[0,50])
    # slo_std
    # draw_three_hist(ground_truth_201707, ground_truth_201807, ground_truth_201907,'slo_std','slope_std_GT',0,5,0.5,[0,85])


    ####### use mapping polygons ####


    os.system('rm processLog.txt')
    # not used, since we move files in the previous steps
    # os.system('rm *.jpg')