#!/usr/bin/env python
# Filename: ArcticDEM_proc 
"""
introduction: prepare ArcticDEM for large area, unzip, crop, registration, and co-registration
             divide the area to many small grids

authors: Huang Lingcao
email:huanglingcao@gmail.com
add time: 26 December, 2020
"""


import os,sys
from optparse import OptionParser

deeplabforRS =  os.path.expanduser('~/codes/PycharmProjects/DeeplabforRS')
sys.path.insert(0, deeplabforRS)
import vector_gpd
import basic_src.map_projection as map_projection
import basic_src.io_function as io_function
import basic_src.basic as basic

import basic_src.RSImageProcess as RSImageProcess
import basic_src.RSImage as RSImage
import basic_src.timeTools as timeTools
import raster_io

import operator

import re
re_stripID='[0-9]{8}_[0-9A-F]{16}_[0-9A-F]{16}'

from urllib.parse import urlparse

from itertools import combinations

import numpy as np

def get_dem_path_in_unpack_tarball(out_dir):
    file_end = ['_dem.tif','_reg_dem.tif']   # Arctic strip and tile (mosaic) version
    for end in file_end:
        dem_tif = os.path.join(out_dir, os.path.basename(out_dir) + end)
        if os.path.isfile(dem_tif):
            return dem_tif
    return False

def subset_image_by_polygon_box(in_img, out_img, polygon,resample_m='bilinear', out_res=None,same_extent=False):
    if same_extent:
        return RSImageProcess.subset_image_by_polygon_box(out_img,in_img,polygon,resample_m=resample_m, xres=out_res,yres=out_res)
    else:
        # crop to the min extent (polygon or the image)
        return RSImageProcess.subset_image_by_polygon_box_image_min(out_img,in_img,polygon,resample_m=resample_m, xres=out_res,yres=out_res)

def process_dem_tarball(tar_list, work_dir,inter_format, out_res, extent_poly=None, poly_id=0, same_extent=False):
    '''
    process dem tarball one by one
    :param tar_list: tarball list
    :param work_dir: working dir, saving the unpacked results
    :param inter_format: format for saving files
    :param out_res: output resolution
    :param extent_poly: extent polygons, in the same projection of the ArcticDEM, if None, then skip
    :param poly_id: extent polygon id, to help the subset filename
    :param same_extent: if true, crop to the same extent (need when do DEM difference)
    :return: a list of final tif files
    '''

    dem_tif_list = []
    tar_folder_list = []
    for targz in tar_list:
        # file existence check
        tar_base = os.path.basename(targz)[:-7]
        # files = io_function.get_file_list_by_pattern(tif_save_dir, tar_base + '*')
        # if len(files) == 1:
        #     basic.outputlogMessage('%s exist, skip processing tarball %s' % (files[0], targz))
        #     dem_tif_list.append(files[0])
        #     continue

        # unpack, it can check whether it has been unpacked
        out_dir = io_function.unpack_tar_gz_file(targz, work_dir)
        if out_dir is not False:
            dem_tif = get_dem_path_in_unpack_tarball(out_dir)
            if os.path.isfile(dem_tif):
                #TODO: registration for each DEM using dx, dy, dz in *reg.txt file
                reg_tif = dem_tif

                # crop
                if extent_poly is None:
                    crop_tif = reg_tif
                else:
                    # because later, we move the file to another foldeer, so we should not use 'VRT' format
                    # crop_tif = RSImageProcess.subset_image_by_shapefile(reg_tif, extent_shp, format=inter_format)
                    save_crop_path = io_function.get_name_by_adding_tail(reg_tif,'sub_poly_%d'%poly_id)
                    if os.path.isfile(save_crop_path):
                        basic.outputlogMessage('%s exists, skip cropping'%save_crop_path)
                        crop_tif = save_crop_path
                    else:
                        crop_tif = subset_image_by_polygon_box(reg_tif,save_crop_path, extent_poly, resample_m='near', out_res = out_res, same_extent=same_extent)
                    if crop_tif is False:
                        basic.outputlogMessage('warning, crop %s faild' % reg_tif)
                        continue
                # # move to a new folder
                # new_crop_tif = os.path.join(tif_save_dir, os.path.basename(crop_tif))
                # io_function.move_file_to_dst(crop_tif, new_crop_tif)
                # dem_tif_list.append(new_crop_tif)
                dem_tif_list.append(crop_tif)
            else:
                basic.outputlogMessage('warning, no *_dem.tif in %s' % out_dir)

            tar_folder_list.append(out_dir)
        else:
            basic.outputlogMessage('warning, unpack %s faild' % targz)

        # break

    return dem_tif_list, tar_folder_list

def group_demTif_yearmonthDay(demTif_list, diff_days=30):
    '''
    groups DEM tif if the acquisition of their raw images is close (less than 30 days or others)
    :param demTif_list:
    :return:
    '''
    dem_groups = {}
    for tif in demTif_list:
        yeardate =  timeTools.get_yeardate_yyyymmdd(os.path.basename(tif))

        b_assgined = False
        for time in dem_groups.keys():
            if timeTools.diff_yeardate(time,yeardate) <= diff_days:
                dem_groups[time].append(tif)
                b_assgined = True
                break
        if b_assgined is False:
            dem_groups[yeardate] = [tif]

    return dem_groups


def group_demTif_strip_pair_ID(demTif_list):
    '''
    group dem tif based on the same pair ID, such as 20170226_1030010066648800_1030010066CDE700 (did not include satellite name)
    :param demTif_list:
    :return:
    '''

    dem_groups = {}
    for tif in demTif_list:
        strip_ids = re.findall(re_stripID, os.path.basename(tif))
        if len(strip_ids) != 1:
            print(strip_ids)
            raise ValueError('found zero or multiple strip IDs in %s, expect one'%tif)
        strip_id = strip_ids[0]
        if strip_id in dem_groups.keys():
            dem_groups[strip_id].append(tif)
        else:
            dem_groups[strip_id] = [tif]

    return dem_groups

def mosaic_dem_same_stripID(demTif_groups,save_tif_dir, resample_method, save_source=False, o_format='GTiff'):
    mosaic_list = []
    for key in demTif_groups.keys():
        save_mosaic = os.path.join(save_tif_dir, key+'.tif')
        # check file existence
        # if os.path.isfile(save_mosaic):
        b_save_mosaic = io_function.is_file_exist_subfolder(save_tif_dir,key+'.tif')
        if b_save_mosaic is not False:
            basic.outputlogMessage('warning, mosaic file: %s exist, skip'%b_save_mosaic)
            mosaic_list.append(b_save_mosaic)
            continue
        # save the source file for producing the mosaic
        if save_source:
            save_mosaic_source_txt = os.path.join(save_tif_dir, key + '_src.txt')
            io_function.save_list_to_txt(save_mosaic_source_txt,demTif_groups[key])

        # if len(demTif_groups[key]) == 1:
        #     io_function.copy_file_to_dst(demTif_groups[key][0],save_mosaic)
        # else:
        #     # RSImageProcess.mosaics_images(dem_groups[key],save_mosaic)
        #     RSImageProcess.mosaic_crop_images_gdalwarp(demTif_groups[key],save_mosaic,resampling_method=resample_method,o_format=o_format)

        # create mosaic, can handle only input one file
        RSImageProcess.mosaic_crop_images_gdalwarp(demTif_groups[key], save_mosaic, resampling_method=resample_method,o_format=o_format,
                                                   compress='lzw',tiled='yes',bigtiff='if_safer')
        mosaic_list.append(save_mosaic)

    return mosaic_list

def mosaic_dem_date(demTif_date_groups,save_tif_dir, resample_method,save_source=False,o_format='GTiff'):

    # convert the key in demTif_date_groups to string
    date_groups = {}
    for key in demTif_date_groups.keys():
        new_key = key.strftime('%Y%m%d') + '_dem'
        date_groups[new_key] = demTif_date_groups[key]

    # becuase the tifs have been grouped, so we can use mosaic_dem_same_stripID
    return mosaic_dem_same_stripID(date_groups,save_tif_dir,resample_method,save_source=save_source,o_format=o_format)

def check_dem_valid_per(dem_tif_list, work_dir, move_dem_threshold = None, area_pixel_num=None):
    '''
    get the valid pixel percentage for each DEM
    :param dem_tif_list:
    :param work_dir:
    :param move_dem_threshold: move a DEM to a sub-folder if its valid percentage small then the threshold
    :return:
    '''

    keep_dem_list = []

    dem_tif_valid_per = {}
    for tif in dem_tif_list:
        # RSImage.get_valid_pixel_count(tif)
        per = RSImage.get_valid_pixel_percentage(tif,total_pixel_num=area_pixel_num)
        dem_tif_valid_per[tif] = per
        keep_dem_list.append(tif)
    # sort
    dem_tif_valid_per_d = dict(sorted(dem_tif_valid_per.items(), key=operator.itemgetter(1), reverse=True))
    percent_txt = os.path.join(work_dir,'dem_valid_percent.txt')
    with open(percent_txt,'w') as f_obj:
        for key in dem_tif_valid_per_d:
            f_obj.writelines('%s %.4f\n'%(os.path.basename(key),dem_tif_valid_per_d[key]))
        basic.outputlogMessage('save dem valid pixel percentage to %s'%percent_txt)

    # only keep dem with valid pixel greater than a threshold
    if move_dem_threshold is not None:  # int or float
        keep_dem_list = []      # reset the list
        mosaic_dir_rm = os.path.join(work_dir,'dem_valid_lt_%.2f'%move_dem_threshold)
        io_function.mkdir(mosaic_dir_rm)
        for tif in dem_tif_valid_per.keys():
            if dem_tif_valid_per[tif] < move_dem_threshold:
                io_function.movefiletodir(tif,mosaic_dir_rm)
            else:
                keep_dem_list.append(tif)

    return keep_dem_list

def dem_diff_newest_oldest(dem_tif_list, out_dem_diff, out_date_diff):
    '''
    get DEM difference, for each pixel, newest vaild value - oldest valid value
    :param dem_list:
    :param output:
    :return:
    '''
    if len(dem_tif_list) < 2:
        basic.outputlogMessage('error, the count of DEM is smaller than 2')
        return False

    if os.path.isfile(out_dem_diff) and os.path.isfile(out_date_diff):
        basic.outputlogMessage('warning, DEM difference already exist, skipping create new ones')
        return True

    out_dem_diff_cm = io_function.get_name_by_adding_tail(out_dem_diff, 'cm')
    if os.path.isfile(out_dem_diff_cm):
        basic.outputlogMessage('warning, DEM difference already exist, skipping create new ones')
        return True

    # groups DEM with original images acquired at the same year months
    dem_groups_date = group_demTif_yearmonthDay(dem_tif_list,diff_days=0)
    # sort based on yeardate in accending order : operator.itemgetter(0)
    dem_groups_date = dict(sorted(dem_groups_date.items(), key=operator.itemgetter(0)))
    io_function.save_dict_to_txt_json('dem_date_for_diff.txt',dem_groups_date)

    date_list = list(dem_groups_date.keys())
    dem_tif_list = [ dem_groups_date[key][0] for key in dem_groups_date.keys()]  # eacy date, only have one tif
    tif_obj_list = [ raster_io.open_raster_read(tif) for tif in dem_tif_list]


    height, width, _ = raster_io.get_width_heigth_bandnum(tif_obj_list[0])

    # check them have the width and height
    for tif, obj in zip(dem_tif_list[1:],tif_obj_list[1:]):
        h, w, _ = raster_io.get_width_heigth_bandnum(obj)
        if h!=height or w!=width:
            raise ValueError('the height and width of %s is different from others'%tif)


    # read all and their date
    date_pair_list = list(combinations(date_list, 2))
    date_diff_list = [ (item[1] - item[0]).days for item in date_pair_list ]
    # sort based on day difference (from max to min)
    date_pair_list_sorted = [x for _, x in sorted(zip(date_diff_list, date_pair_list),reverse=True)]    # descending

    # use dict to read data from disk (only need)
    dem_data_dict = {}

    # get the difference
    date_diff_np = np.zeros((height, width),dtype=np.uint16)
    dem_diff_np = np.empty((height, width),dtype=np.float32)
    dem_diff_np[:] = np.nan

    for pair in date_pair_list_sorted:
        diff_days = (pair[1] - pair[0]).days
        basic.outputlogMessage('Getting DEM difference using the one on %s and %s, total day diff: %d'%
                               (timeTools.date2str(pair[1]), timeTools.date2str(pair[0]),diff_days))
        # print(pair,':',(pair[1] - pair[0]).days)

        # read data to memory if need
        if pair[0] not in dem_data_dict.keys():
            data_old = raster_io.read_raster_one_band_np( dem_groups_date[pair[0]][0] )
            dem_data_dict [pair[0]] = data_old
        else:
            data_old = dem_data_dict[pair[0]]

        # read data to memory if need
        if pair[1] not in dem_data_dict.keys():
            data_new = raster_io.read_raster_one_band_np( dem_groups_date[pair[1]][0] )
            dem_data_dict [pair[1]] = data_new
        else:
            data_new = dem_data_dict [pair[1]]

        print('data_old shape:',data_old.shape)
        print('data_new shape:',data_new.shape)

        diff_two = data_new - data_old
        # print(diff_two)

        # fill the element
        new_ele = np.where(np.logical_and( np.isnan(dem_diff_np), ~np.isnan(diff_two)))
        dem_diff_np[ new_ele ] = diff_two[new_ele]

        date_diff_np[new_ele] = diff_days

        # check if all have been filled ( nan pixels)
        diff_remain_hole = np.where(np.isnan(dem_diff_np))
        basic.outputlogMessage(' remain %.4f percent pixels need to be filled'% (100.0*diff_remain_hole[0].size/dem_diff_np.size) )
        if diff_remain_hole[0].size < 1:
            break

        # # test
        # break
    # save date diff to tif (16 bit)
    raster_io.save_numpy_array_to_rasterfile(date_diff_np,out_date_diff,dem_tif_list[0], nodata=0,compress='lzw',tiled='yes',bigtiff='if_safer')

    # # stretch the DEM difference, save to 8 bit.
    # dem_diff_np_8bit = raster_io.image_numpy_to_8bit(dem_diff_np,10,-10,dst_nodata=0)
    # out_dem_diff_8bit = io_function.get_name_by_adding_tail(out_dem_diff, '8bit')
    # raster_io.save_numpy_array_to_rasterfile(dem_diff_np_8bit, out_dem_diff_8bit, dem_tif_list[0], nodata=0)


    # if possible, save to 16 bit, to save the disk storage.
    # dem_diff_np[0:5,0] = -500
    # dem_diff_np[0,0:5] = 500
    # print(np.nanmin(dem_diff_np))
    # print(np.nanmax(dem_diff_np))
    range = np.iinfo(np.int16)
    dem_diff_np_cm = dem_diff_np*100
    if np.nanmin(dem_diff_np_cm) < range.min or np.nanmax(dem_diff_np_cm) > range.max:
        # save dem diff to files (float), meter
        raster_io.save_numpy_array_to_rasterfile(dem_diff_np,out_dem_diff,dem_tif_list[0],nodata=-9999,compress='lzw',tiled='yes',bigtiff='if_safer')
    else:
        # save dem diff to 16bit, centimeter, only handle diff from -327.67 to 327.67 meters
        dem_diff_np_cm = dem_diff_np_cm.astype(np.int16)        # save to int16
        raster_io.save_numpy_array_to_rasterfile(dem_diff_np_cm, out_dem_diff_cm, dem_tif_list[0],nodata=32767,compress='lzw',tiled='yes',bigtiff='if_safer')


    return True

def coregistration_dem():
    pass

def process_arcticDEM_tiles(tar_list,save_dir,inter_format, resample_method, o_res, extent_poly, extent_id, pre_name, b_rm_inter=True):
    '''
    process the mosaic (not multi-temporal) version of ArcticDEM
    :param tar_list:
    :param save_dir:
    :param inter_format:
    :param resample_method:
    :param o_res: output resolution
    :param extent_poly:  extent polygons, in the same projection of ArcticDEM
    :param extent_id:  extent id
    :param pre_name:
    :param b_rm_inter:
    :return:
    '''

    # unpackage and crop to extent
    dem_tif_list, tar_folders = process_dem_tarball(tar_list, save_dir, inter_format, o_res, extent_poly=extent_poly, poly_id=extent_id)
    if len(dem_tif_list) < 1:
        raise ValueError('No DEM extracted from tarballs')

    dem_name = os.path.basename(tar_folders[0])[-7:]

    save_path = os.path.join(save_dir, pre_name + '_' + dem_name + '_ArcticTileDEM_sub_%d.tif'%extent_id )

    RSImageProcess.mosaic_crop_images_gdalwarp(dem_tif_list, save_path, resampling_method=resample_method,o_format=inter_format,
                                               xres=o_res,yres=o_res, compress='lzw',tiled='yes',bigtiff='if_safer')

    # remove intermediate files
    if b_rm_inter:
        basic.outputlogMessage('remove intermediate files')
        for folder in tar_folders:
            io_function.delete_file_or_dir(folder)

    return True

def is_ArcticDEM_tiles(tar_list):
    '''
    check whether it is mosaic version (tiles) of DEM
    :param tar_list:
    :return:
    '''
    tile_pattern = '^\d{2}_\d{2}_'
    for tar in tar_list:
        tar_base = os.path.basename(tar)
        tiles = re.findall(tile_pattern,tar_base)
        if len(tiles) == 1:
            pass
        else:
            basic.outputlogMessage('%s is not a tile of ArcticDEM'%tar)
            return False

    return True

def get_tar_list_sub(tar_dir, dem_polygons,dem_urls,extent_poly):

    dem_poly_ids = vector_gpd.get_poly_index_within_extent(dem_polygons, extent_poly)
    urls = [dem_urls[id] for id in dem_poly_ids]

    new_tar_list = []
    for ii, url in enumerate(urls):
        tmp = urlparse(url)
        filename = os.path.basename(tmp.path)
        save_dem_path = os.path.join(tar_dir, filename)
        if os.path.isfile(save_dem_path):
            new_tar_list.append(save_dem_path)
        else:
            basic.outputlogMessage('Warning, %s not in %s, may need to download it first'%(filename,tar_dir))

    return new_tar_list



def proc_ArcticDEM_tile_one_grid_polygon(tar_dir,dem_polygons,dem_urls,o_res,save_dir,inter_format,b_rm_inter,extent_poly, extent_id,
                                         pre_name,resample_method='average'):

    # get file in the tar_dir
    tar_list = get_tar_list_sub(tar_dir, dem_polygons,dem_urls,extent_poly)
    if len(tar_list) < 1:
        basic.outputlogMessage('Warning, no tarball for the extent (id=%d) in %s'%(extent_id,tar_dir))
        return False

    process_arcticDEM_tiles(tar_list, save_dir, inter_format, resample_method,o_res, extent_poly,extent_id,pre_name, b_rm_inter=b_rm_inter)

    pass

def proc_ArcticDEM_strip_one_grid_polygon(tar_dir,dem_polygons,dem_urls,o_res,save_dir,inter_format,b_mosaic_id,b_mosaic_date,b_rm_inter,
                                    b_dem_diff,extent_poly, extent_id,keep_dem_percent,pre_name,resample_method='average',same_extent=False):

    # get file in the tar_dir
    tar_list = get_tar_list_sub(tar_dir, dem_polygons,dem_urls,extent_poly)
    if len(tar_list) < 1:
        basic.outputlogMessage('Warning, no tarball for the extent (id=%d) in %s'%(extent_id,tar_dir))
        return False

    # unpackage and crop to extent
    dem_tif_list, tar_folders = process_dem_tarball(tar_list, save_dir, inter_format, o_res, extent_poly=extent_poly, poly_id=extent_id,same_extent=same_extent)
    if len(dem_tif_list) < 1:
        raise ValueError('No DEM extracted from tarballs')

    # area pixel count
    area_pixel_count = int(extent_poly.area / (o_res*o_res))
    basic.outputlogMessage('Area pixel count: %d'%area_pixel_count)

    # groups DEM
    dem_groups = group_demTif_strip_pair_ID(dem_tif_list)

    # create mosaic (dem with the same strip pair ID)
    mosaic_dir = os.path.join(save_dir,'dem_stripID_mosaic_sub_%d'%extent_id)
    if b_mosaic_id:
        if os.path.isfile(os.path.join(mosaic_dir,'dem_valid_percent.txt')):
            basic.outputlogMessage('mosaic based on stripID exists, skip mosaicking')
            with open(os.path.join(mosaic_dir,'dem_valid_percent.txt')) as f_job:
                tif_names = [ line.split()[0]  for line in f_job.readlines() ]
                dem_tif_list = [os.path.join(mosaic_dir,item) for item in tif_names]
                # print(dem_tif_list)
        else:
            io_function.mkdir(mosaic_dir)
            mosaic_list = mosaic_dem_same_stripID(dem_groups,mosaic_dir,resample_method,o_format=inter_format)
            dem_tif_list = mosaic_list

            # get valid pixel percentage
            dem_tif_list = check_dem_valid_per(dem_tif_list,mosaic_dir,move_dem_threshold = keep_dem_percent, area_pixel_num=area_pixel_count)

    # groups DEM with original images acquired at the same year months
    dem_groups_date = group_demTif_yearmonthDay(dem_tif_list,diff_days=31)
    # sort based on yeardate in accending order : operator.itemgetter(0)
    dem_groups_date = dict(sorted(dem_groups_date.items(), key=operator.itemgetter(0)))
    # save to txt (json format)
    year_date_txt = os.path.join(mosaic_dir, 'year_date_tif.txt')
    io_function.save_dict_to_txt_json(year_date_txt,dem_groups_date)

    # merge DEM with close acquisition date
    mosaic_yeardate_dir = os.path.join(save_dir,'dem_date_mosaic_sub_%d'%extent_id)
    if b_mosaic_date:
        if os.path.isfile(os.path.join(mosaic_yeardate_dir,'dem_valid_percent.txt')):
            basic.outputlogMessage('mosaic based on acquisition date exists, skip mosaicking')
            with open(os.path.join(mosaic_yeardate_dir,'dem_valid_percent.txt')) as f_job:
                tif_names = [ line.split()[0]  for line in f_job.readlines() ]
                dem_tif_list = [os.path.join(mosaic_yeardate_dir,item) for item in tif_names]
                # print(dem_tif_list)
        else:
            io_function.mkdir(mosaic_yeardate_dir)
            # this is the last output of mosaic, save to 'GTiff' format.
            mosaic_list = mosaic_dem_date(dem_groups_date,mosaic_yeardate_dir,resample_method, save_source=True, o_format='GTiff')
            dem_tif_list = mosaic_list

            # get valid pixel percentage
            dem_tif_list = check_dem_valid_per(dem_tif_list,mosaic_yeardate_dir,move_dem_threshold = keep_dem_percent,area_pixel_num=area_pixel_count)




    # co-registration


    # do DEM difference
    if b_dem_diff:
        save_dem_diff = os.path.join(save_dir,pre_name + '_ArcticDEM_diff_sub_%d.tif'%extent_id)
        save_date_diff = os.path.join(save_dir,pre_name + '_date_diff_sub_%d.tif'%extent_id)
        dem_diff_newest_oldest(dem_tif_list,save_dem_diff,save_date_diff)

        pass

    # remove intermediate files
    if b_rm_inter:
        basic.outputlogMessage('remove intermediate files')
        for folder in tar_folders:
            io_function.delete_file_or_dir(folder)

        # remove the mosaic folders
        if b_dem_diff:
            io_function.delete_file_or_dir(mosaic_dir)
            io_function.delete_file_or_dir(mosaic_yeardate_dir)

    pass

def test_dem_diff():
    # test in folder "~/Data/Arctic/canada_arctic/DEM/WR_dem"
    extent_id = 1
    mosaic_yeardate_dir = os.path.join('./', 'dem_date_mosaic_sub_%d' % extent_id)
    with open(os.path.join(mosaic_yeardate_dir, 'dem_valid_percent.txt')) as f_job:
        tif_names = [line.split()[0] for line in f_job.readlines()]
        dem_tif_list = [os.path.join(mosaic_yeardate_dir, item) for item in tif_names]

    save_dem_diff = 'test' + '_ArcticDEM_diff_sub_%d.tif' % extent_id
    save_date_diff = 'test' + '_date_diff_sub_%d.tif' % extent_id
    dem_diff_newest_oldest(dem_tif_list, save_dem_diff, save_date_diff)
    pass


def main(options, args):

    # # test
    # return test_dem_diff()

    extent_shp = args[0]
    # ext_shp_prj = map_projection.get_raster_or_vector_srs_info_epsg(extent_shp)
    # reproject if necessary, it seems that the gdalwarp can handle different projection
    # if ext_shp_prj != 'EPSG:3413':  # EPSG:3413 is the projection ArcticDEM used
    #     extent_shp_reprj = io_function.get_name_by_adding_tail(extent_shp,'3413')
    #     vector_gpd.reproject_shapefile(extent_shp,'EPSG:3413',extent_shp_reprj)
    #     extent_shp = extent_shp_reprj

    tar_dir = options.ArcticDEM_dir
    save_dir = options.save_dir
    b_mosaic_id = options.create_mosaic_id
    b_mosaic_date = options.create_mosaic_date
    b_rm_inter = options.remove_inter_data
    keep_dem_percent = options.keep_dem_percent
    inter_format = options.format
    arcticDEM_shp = options.arcticDEM_shp
    o_res = options.out_res
    b_dem_diff = options.create_dem_diff

    extent_shp_base = os.path.splitext(os.path.basename(extent_shp))[0]

    dem_prj = map_projection.get_raster_or_vector_srs_info_epsg(arcticDEM_shp)
    extent_prj = map_projection.get_raster_or_vector_srs_info_epsg(extent_shp)
    if extent_prj == dem_prj:
        extent_polys = vector_gpd.read_polygons_gpd(extent_shp)
    else:
        extent_polys = vector_gpd.read_shape_gpd_to_NewPrj(extent_shp,dem_prj)

    if len(extent_polys) < 1:
        raise ValueError('No polygons in %s'%extent_shp)
    else:
        basic.outputlogMessage('%d extent polygons in %s'%(len(extent_polys),extent_shp))

    extPolys_ids = vector_gpd.read_attribute_values_list(extent_shp,'id')
    if extPolys_ids is None:
        basic.outputlogMessage('Warning, field: id is not in %s, will create default ID for each grid'%extent_shp)
        extPolys_ids = [ id + 1 for id in range(len(extent_polys))]

    # read dem polygons and url
    dem_polygons = vector_gpd.read_polygons_gpd(arcticDEM_shp)
    dem_urls = vector_gpd.read_attribute_values_list(arcticDEM_shp,'fileurl')
    basic.outputlogMessage('%d dem polygons in %s' % (len(dem_polygons), extent_shp))

    # get tarball list
    tar_list = io_function.get_file_list_by_ext('.gz',tar_dir,bsub_folder=False)
    if len(tar_list) < 1:
        raise ValueError('No input tar.gz files in %s'%tar_dir)

    b_ArcticDEM_tiles = False
    if is_ArcticDEM_tiles(tar_list):
        basic.outputlogMessage('Input is the mosaic version of ArcticDEM')
        b_ArcticDEM_tiles = True

    same_extent = False
    if b_dem_diff:
        # crop each one to the same extent, easy for DEM differnce.
        same_extent = True

    for idx, ext_poly in zip(extPolys_ids,extent_polys):
        basic.outputlogMessage('get data for the %d th extent (%d in total)' % (idx, len(extent_polys)))

        if b_ArcticDEM_tiles:
            proc_ArcticDEM_tile_one_grid_polygon(tar_dir,dem_polygons,dem_urls,o_res,save_dir,inter_format,b_rm_inter,ext_poly, idx,extent_shp_base)
        else:

            proc_ArcticDEM_strip_one_grid_polygon(tar_dir,dem_polygons, dem_urls, o_res,save_dir,inter_format,
                                                  b_mosaic_id,b_mosaic_date,b_rm_inter, b_dem_diff,
                                                  ext_poly,idx,keep_dem_percent, extent_shp_base, resample_method='average',same_extent=same_extent)




if __name__ == "__main__":

    usage = "usage: %prog [options] extent_shp "
    parser = OptionParser(usage=usage, version="1.0 2020-12-26")
    parser.description = 'Introduction: get data list within an extent  '
    # parser.add_option("-x", "--save_xlsx_path",
    #                   action="store", dest="save_xlsx_path",
    #                   help="save the sence lists to xlsx file")


    parser.add_option("-a", "--ArcticDEM_dir",
                      action="store", dest="ArcticDEM_dir",default='./',
                      help="the folder saving downloaded ArcticDEM tarballs")

    parser.add_option("-d", "--save_dir",
                      action="store", dest="save_dir",default='./',
                      help="the folder to save pre-processed results")

    parser.add_option("-s", "--arcticDEM_shp",
                      action="store", dest="arcticDEM_shp",
                      help="if the extent shapefile contains multiple polygons, we need the shapefile of ArcticDEM")

    parser.add_option("-p", "--keep_dem_percent",
                      action="store", dest="keep_dem_percent",type=float,default=30.0,
                      help="keep dem with valid percentage greater than this value")

    parser.add_option("-o", "--out_res",
                      action="store", dest="out_res",type=float,default=2.0,
                      help="the resolution for final output")

    parser.add_option("-m", "--create_mosaic_id",
                      action="store_true", dest="create_mosaic_id",default=False,
                      help="for a small region, if true, then get a mosaic of dem with the same ID (date_catalogID_catalogID)")

    parser.add_option("-t", "--create_mosaic_date",
                      action="store_true", dest="create_mosaic_date",default=False,
                      help="for a small region, if true, then get a mosaic of dem with close acquisition date ")

    parser.add_option("-c", "--create_dem_diff",
                      action="store_true", dest="create_dem_diff",default=False,
                      help="True to create DEM difference, c for change")

    parser.add_option("-r", "--remove_inter_data",
                      action="store_true", dest="remove_inter_data",default=False,
                      help="True to keep intermediate data")

    # there is one mosaic: Failed to compute statistics, no valid pixels found in sampling, other are ok,
    # so, may still use GTiff format.
    # TODO: need to check, 'VRT' format maybe is good.
    parser.add_option("-f", "--format",
                      action="store", dest="format", default='GTiff',  #default='VRT',
                      help="the data format for middle intermediate files")

    (options, args) = parser.parse_args()
    # print(options.create_mosaic)

    if len(sys.argv) < 2 or len(args) < 1:
        parser.print_help()
        sys.exit(2)

    main(options, args)
