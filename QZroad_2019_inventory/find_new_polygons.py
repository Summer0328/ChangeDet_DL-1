#!/usr/bin/env python
# Filename: find_new_polygons 
"""
introduction: compare two shapefile, and return new polygons, at a specific location, there is no polygon in the previous results

authors: Huang Lingcao
email:huanglingcao@gmail.com
add time: 28 July, 2020
"""

import sys,os
import pandas as pd

sys.path.insert(0,os.path.expanduser('~/codes/PycharmProjects/DeeplabforRS'))
import vector_gpd
import basic_src.io_function as io_function
from basic_src.map_projection import get_raster_or_vector_srs_info_proj4

res_dir = os.path.expanduser('~/Data/Qinghai-Tibet/QZrailroad_buffer_area/autoMapping')

# new_path = os.path.join(res_dir,'QZ_deeplabV3+_2/result_backup/QZ_deeplabV3+_2_exp2_iter30000_QZroad_2019.shp')
new_path = os.path.join(res_dir,'QZ_deeplabV3+_2/result_backup/QZ_deeplabV3+_2_exp3_iter30000_QZroad_2019.shp')

old_path = os.path.join(res_dir,'QZ_deeplabV3+_2/result_backup/QZ_deeplabV3+_2_exp1_iter30000_QZroad_2019.shp')
# old_path2 = os.path.expanduser('~/Data/Qinghai-Tibet/QZrailroad_buffer_area/thaw_slumps_for_training/qz_manu_RTS_utm_201907_08_v2.shp')
old_path2 = os.path.expanduser('~/Data/Qinghai-Tibet/QZrailroad_buffer_area/thaw_slumps_for_training/qz_manu_RTS_utm_201907_08_v3_edit.shp')

old_path3 = os.path.join(res_dir,'QZ_deeplabV3+_2/result_backup/QZ_deeplabV3+_2_exp2_iter30000_QZroad_2019.shp')

old_path_list = [old_path, old_path2,old_path3]

# check projection

new_prj = get_raster_or_vector_srs_info_proj4(new_path)
for poly_path in old_path_list:
    old_prj = get_raster_or_vector_srs_info_proj4(poly_path)
    if old_prj != new_prj:
        raise ValueError('inconsistent projection between %s and %s'%(new_path, poly_path))

# get new polygons
new_polygons = vector_gpd.read_polygons_gpd(new_path)

old_polygons = []
for poly_path in old_path_list:
    polygons = vector_gpd.read_polygons_gpd(poly_path)
    old_polygons.extend(polygons)

true_new_polygon_list = []
for idx,poly in enumerate(new_polygons):
    print('process the %d th polygon, total: %d'%(idx+1,len(new_polygons)))
    b_find = False
    for old_poly in old_polygons:
        inter = poly.intersection(old_poly)
        if inter.is_empty is False:
            b_find = True
            break
    if b_find is False:
        true_new_polygon_list.append(poly)

# save to file
save_path = io_function.get_name_by_adding_tail(new_path,'NEW_polygons')

# save results
save_polyons_attributes = {}
save_polyons_attributes["Polygons"] = true_new_polygon_list
polygon_df = pd.DataFrame(save_polyons_attributes)

vector_gpd.save_polygons_to_files(polygon_df, 'Polygons', new_prj, save_path)
print('save to %s'%save_path)










