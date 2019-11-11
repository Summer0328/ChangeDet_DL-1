#!/usr/bin/env bash

## Introduction:  download and crop s2 images

#authors: Huang Lingcao
#email:huanglingcao@gmail.com
#add time: 11 November, 2019

# Exit immediately if a command exits with a non-zero status. E: error trace
set -eE -o functrace

co_dir=~/codes/PycharmProjects/ChangeDet_DL


shp=~/Data/Qinghai-Tibet/qtp_thaw_slumps/rts_polygons_s2_2018/qtp_train_polygons_s2_2018_v2.shp
save_dir=s2_download
start_date=2015-01-01
end_date=2017-11-01
could_cover=0.5

${co_dir}/dataTools/download_s2_images.py ${shp} ${save_dir}  -s ${start_date} -e ${end_date} -c ${could_cover}