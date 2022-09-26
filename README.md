# cvat_export_scripts
This repository contains a collection of custom cvat export scripts. The scripts are intended with the use for [cvat](https://github.com/opencv/cvat).<br/>
**NOTE**: This repository is **NOT by/from the developers of cvat!** If you need cvat support, please go to the original github repository! 
<br/>
<br/>
The purpose of this script is to use the cli provided in cvat to export the datasets in a more adequate folder-structure.<br/>
<br/>
Note: These scripts are only compatible for version 2.1 of cvat!<br/>
<br/>
**MOT 1.1**
The folder structure is split into train/test/validation. Each task is considered as a sequence i.e a video. That means each task is exported as a folder into train/test/validation accordingly.<br/>
<br/>
The .seqinfo is created as well, altough not filled completly yet. You'll have to insert your own code. The images are stored in a subfolder called img1, the groundtruth in a subfolder gt.<br/>
<br/>
**YOLO 1.1**
The export follows convention of Ultralytics [custom dataset](https://github.com/ultralytics/yolov5/blob/master/README.md)<br/>
<br/>
Note: The generated .yaml file is **NOT** correct per default. You'll have to add the possible classifications afterwards. 
<br/>

## Installation
You'll need to link to your cli instance of cvat. For this clone the repository of cvat with the same version as your cvat server instance.</br>
</br>
The you have to adapt the python-variable in each script: </br>
```
CVAT_CODE_LOCATION="/path/to/cvat/utils/cli"
```


## Usage

If you want export all datasets from your cvat server in the MOT 1.1 format: <br/>
```
python export_mot.py --output <path/to/my/location>
```
Note: In the output folder there is going to be created a folder for each project in the cvat server!<br/>
<br/>
If you want export all datasets from your cvat server in the YOLO 1.1 format:<br/>
```
python export_yolo.py --output <path/to/my/location>
```
Note: In the output folder there is going to be created a folder for each project in the cvat server!<br/>
o
## Requirements

You need to clone the original cvat repository

```
pip install tqdm
pip install pexpect
```


