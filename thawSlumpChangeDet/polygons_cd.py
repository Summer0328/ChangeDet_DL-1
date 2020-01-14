#!/usr/bin/env python
# Filename: polygons_cd 
"""
introduction: change detection for two groups of polygons (in two shape files)

authors: Huang Lingcao
email:huanglingcao@gmail.com
add time: 05 January, 2020
"""

import sys,os
from optparse import OptionParser

# added path of DeeplabforRS
sys.path.insert(0, os.path.expanduser('~/codes/PycharmProjects/DeeplabforRS'))
import basic_src.io_function as io_function
import basic_src.basic as basic
import basic_src.map_projection as map_projection
import parameters

import vector_gpd

import pandas as pd
import geopandas as gpd
# from geopandas import GeoSeries

# for polygon comparison


def polygons_change_detection(old_shp_path, new_shp_path,expand_save_path,shrink_save_path):
    '''
    change detection of polygons, compare their extent changes (only get the expanding part)
    :param old_shp_path: the path of the old polygons
    :param new_shp_path: the path of the new polygons
    :param expand_save_path: save path, the expanding area
    :param shrink_save_path: save path, the shrinking part (thaw slumps cannot shrink, the shrinking part is due to delineation error)
    :return: True if successfully, False otherwise
    '''
    # check projection of the shape file, should be the same
    new_shp_proj4 = map_projection.get_raster_or_vector_srs_info_proj4(new_shp_path)
    old_shp_proj4 = map_projection.get_raster_or_vector_srs_info_proj4(old_shp_path)
    if new_shp_proj4 != old_shp_proj4:
        raise ValueError('error, projection insistence between %s and %s'%(new_shp_proj4, old_shp_proj4))

    # read old polygons as shapely objects
    old_polygons = vector_gpd.read_polygons_gpd(old_shp_path)
    if len(old_polygons) < 1:
        raise ValueError('No polygons in %s' % old_shp_path)

    old_polygon_absent = [True] * len(old_polygons)

    change_type_list = []  # 1 for expanding and 2 for new
    polygon_expand_list = []
    old_file_name = []
    old_polygon_idx = []
    new_file_name = []
    new_polygon_idx = []

    polygon_shrink_list = []
    shrink_change_type_list = []    # 3 for shrinking 4 for disappear
    shrink_old_file_name = []
    shrink_old_polygon_idx = []
    shrink_new_file_name = []
    shrink_new_polygon_idx = []


    # read new polygons
    new_polygons = vector_gpd.read_polygons_gpd(new_shp_path)
    if len(new_polygons) < 1:
        raise ValueError('No polygons in %s'% new_shp_path)

    # compare these two groups of polygons:
    # changes include: (1) new, (2) absence, and (3) expanding or shrinking (thaw slumps)
    for idx_new, a_new_polygon in enumerate(new_polygons):

        b_is_new = True

        # find expanding or shrinking parts (two polygons must have overlap)
        intersec_poly_index_list = []        # a new polygon may intersect more than one old polygons
        for idx_old, a_old_polygon in enumerate(old_polygons):
            intersection = a_old_polygon.intersection(a_new_polygon)
            if intersection.is_empty is True:
                continue
            else:
                intersec_poly_index_list.append(idx_old)

                # indicate that this polygon is not absent
                old_polygon_absent[idx_old] = False

        if len(intersec_poly_index_list) > 1:
            basic.outputlogMessage('Warning, the %dth new polygon intersect %d old polygon'%(idx_new, len(intersec_poly_index_list)))

        # calculate the expanding or shrinking
        for intersec_old_index in intersec_poly_index_list:

            # for difference operation as follows, only the expanding part of a_new_polygon will be output, that is good.
            # if want to get the shrinking part, we should use a_old_polygon.difference(a_new_polygon), but thaw slumps cannot shrink
            a_old_polygon = old_polygons[intersec_old_index]
            polygon_expand = a_new_polygon.difference(a_old_polygon)
            polygon_expand_list.append(polygon_expand)

            polygon_shrink = a_old_polygon.difference(a_new_polygon)
            polygon_shrink_list.append(polygon_shrink)

            b_is_new = False
            new_file_name.append(os.path.basename(new_shp_path))
            new_polygon_idx.append(idx_new)

            old_file_name.append(os.path.basename(old_shp_path))
            old_polygon_idx.append(intersec_old_index)

            change_type_list.append(1)  # expanding

            shrink_change_type_list.append(3)   # shrinking
            shrink_old_file_name.append(os.path.basename(old_shp_path))
            shrink_old_polygon_idx.append(intersec_old_index)
            shrink_new_file_name.append(os.path.basename(new_shp_path))
            shrink_new_polygon_idx.append(idx_new)

        # if it is new
        if b_is_new:
            change_type_list.append(2)  # new
            new_file_name.append(os.path.basename(new_shp_path))
            new_polygon_idx.append(idx_new)
            old_file_name.append('None')
            old_polygon_idx.append(-9999)
            polygon_expand_list.append(a_new_polygon)

    # find absent polygons in the old set of polygons
    absent_indices = [i for i, x in enumerate(old_polygon_absent) if x == True]
    if len(absent_indices) < 1:
        basic.outputlogMessage('No polygon disappear in %s' % old_shp_path)
    else:
        absent_indices = [ value for value in absent_indices]     # value+1
        # basic.outputlogMessage('Disappeared Polygons in %s: (index from 1) %s' % (old_shp_path, str(absent_indices)))
        for absent_index in absent_indices:
            shrink_change_type_list.append(4)  # absence (disappear)
            polygon_shrink_list.append(old_polygons[absent_index])
            shrink_old_file_name.append(os.path.basename(old_shp_path))
            shrink_old_polygon_idx.append(absent_index)
            shrink_new_file_name.append('None')
            shrink_new_polygon_idx.append(-9999)

    # save the polygon changes
    expanding_df = pd.DataFrame({'ChangeType': change_type_list,
                                 'old_file': old_file_name,
                                 'old_index': old_polygon_idx,
                                 'new_file': new_file_name,
                                 'new_index': new_polygon_idx,
                                 'PolygonExpand': polygon_expand_list
                                })
    shrinking_df = pd.DataFrame({'ChangeType': shrink_change_type_list,
                                 'old_file': shrink_old_file_name,
                                 'old_index': shrink_old_polygon_idx,
                                 'new_file': shrink_new_file_name,
                                 'new_index': shrink_new_polygon_idx,
                                 'PolygonShrink': polygon_shrink_list
                                })

    wkt_string = map_projection.get_raster_or_vector_srs_info_wkt(old_shp_path)
    vector_gpd.save_polygons_to_files(expanding_df,'PolygonExpand', wkt_string, expand_save_path)
    vector_gpd.save_polygons_to_files(shrinking_df,'PolygonShrink', wkt_string, shrink_save_path)

    return True

def Multipolygon_to_Polygons(input_shp, ouptput_shp):
    '''
    convert each multiPolygon to polygons
    :param input_shp:
    :param ouptput_shp:
    :return:
    '''

    # read polygons as shapely objects
    shapefile = gpd.read_file(input_shp)
    attribute_names = None
    polygon_attributes_list = [] # 2d list
    polygon_list = []   #

    # go through each MULTIPOLYGON
    for idx,row in shapefile.iterrows():
        if idx==0:
            attribute_names = row.keys().to_list()
            attribute_names = attribute_names[:len(attribute_names)-1]
            # basic.outputlogMessage("attribute names: "+ str(row.keys().to_list()))

        multiPolygon = row['geometry']
        if multiPolygon.geom_type == 'MultiPolygon':
            polygons = list(multiPolygon)
        elif multiPolygon.geom_type == 'Polygon':
            polygons = [multiPolygon]
        else:
            raise ValueError('Currently, only support Polygon and MultiPolygon, but input is %s' % multiPolygon.geom_type)

        for p_idx, polygon in enumerate(polygons):
            # print(polyon.area)
            polygon_attributes = row[:len(row)-1].to_list()

            # calculate area, circularity, oriented minimum bounding box
            polygon_shape = vector_gpd.calculate_polygon_shape_info(polygon)
            if idx == 0 and p_idx==0:
                [attribute_names.append(item) for item in polygon_shape.keys()]

            [polygon_attributes.append(polygon_shape[item]) for item in polygon_shape.keys()]
            polygon_attributes_list.append(polygon_attributes)
            polygon_list.append(polygon)

    # save results
    save_polyons_attributes = {}
    for idx, attribute in enumerate(attribute_names):
        # print(idx, attribute)
        values = [item[idx] for item in polygon_attributes_list]
        save_polyons_attributes[attribute] = values

    save_polyons_attributes["Polygons"] = polygon_list
    polygon_df = pd.DataFrame(save_polyons_attributes)

    wkt_string = map_projection.get_raster_or_vector_srs_info_wkt(input_shp)
    return vector_gpd.save_polygons_to_files(polygon_df, 'Polygons', wkt_string, ouptput_shp)

def expanding_change_post_processing(input_shp, save_path, min_area_thr, min_circularity_thr):
    '''
    post-processing for expanding changes (polygons)
    :param input_shp: a shape file containing the polygons (derived from multiPolygons)
    :param save_path: save path
    :return:
    '''
    # read polygons as shapely objects
    shapefile = gpd.read_file(input_shp)

    # go through each polygon
    for idx,row in shapefile.iterrows():

        polygon = row['geometry']
        # go through post-processing to decide to keep or remove it
        # only keep polygons with large areas and move toward upslope
        if polygon.area < min_area_thr or row['circularit'] < min_circularity_thr:
            shapefile.drop(idx, inplace=True)
            # continue

    # save results
    shapefile.to_file(save_path, driver='ESRI Shapefile')

    pass

def main(options, args):

    old_shp_path = args[0]
    new_shp_path = args[1]

    # check files do exist
    assert io_function.is_file_exist(new_shp_path)
    assert io_function.is_file_exist(old_shp_path)

    para_file = options.para_file

    # conduct change detection
    if options.output is None:
        output_path = 'change_'+ os.path.splitext(os.path.basename(old_shp_path))[0] + '_' \
                      + os.path.splitext(os.path.basename(new_shp_path))[0] + '.shp'
    else:
        output_path = options.output

    basic.outputlogMessage('Conduct change detection on %s and %s, and the results will be saved to %s'%
                           (old_shp_path, new_shp_path, output_path))

    main_shp_name = os.path.splitext(os.path.basename(old_shp_path))[0] + '_' \
                         + os.path.splitext(os.path.basename(new_shp_path))[0] + '.shp'
    # get expanding and shrinking parts
    output_path_expand = 'expand_' + main_shp_name
    output_path_shrink = 'shrink_' + main_shp_name
    polygons_change_detection(old_shp_path, new_shp_path, output_path_expand,output_path_shrink)

    # multi polygons to polygons, then add some information on the polygons
    all_change_polygons = 'all_changes_' + main_shp_name
    Multipolygon_to_Polygons(output_path_expand, all_change_polygons)

    # post-processing of the expanding parts, to get the real expanding part (exclude delineation errors)
    min_area_thr = parameters.get_digit_parameters_None_if_absence(para_file, 'minimum_change_area', 'float')
    min_circularity_thr = parameters.get_digit_parameters_None_if_absence(para_file,'minimum_change_circularity', 'float')
    expanding_change_post_processing(all_change_polygons, output_path, min_area_thr, min_circularity_thr)


if __name__ == "__main__":
    usage = "usage: %prog [options] old_shape_file new_shape_file "
    parser = OptionParser(usage=usage, version="1.0 2020-01-05")
    parser.description = 'Introduction: conduct change detection for two groups of polygons '

    parser.add_option("-p", "--para",
                      action="store", dest="para_file",
                      help="the parameters file")

    parser.add_option('-o', '--output',
                      action="store", dest = 'output',
                      help='the path to save the change detection results')

    (options, args) = parser.parse_args()
    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(2)

    # set parameters files
    if options.para_file is None:
        print('error, no parameters file')
        parser.print_help()
        sys.exit(2)
    else:
        parameters.set_saved_parafile_path(options.para_file)

    basic.setlogfile('polygons_changeDetection.log')

    main(options, args)


