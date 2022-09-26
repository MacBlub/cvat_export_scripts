#!/bin/python
# This a linux script! No windows formatted paths yet supported...

import re
import os
import json
import tqdm
import getpass
import pexpect
import subprocess
import pathlib
import logging
import argparse

# Issues:
# - Saving videos as images is space consuming
# - The quality of the images is lacking. Could be compression issues...

# Server Login
USER=""
PASSWORD=""

# Location & Commands for cvat cli
CVAT_CODE_LOCATION="/path/to/cvat/utils/cli"

# Note: CMD[0-9] are commands used throughout program

# Logging
logging.basicConfig(level=logging.INFO)

def parse_args():
    parser = argparse.ArgumentParser(description='Extract the datasets from cvat server on this machine')
    parser.add_argument('--output', dest='output', action='store', required=True,
                    nargs=1, help='Output location (path) where the dataset is written to.')
    return parser.parse_args()

def cache_server_password(): # WARN : This seems to be not very secure...
    global USER, PASSWORD
    logging.info("[DATASET] : Prompting User for Username and Password!")
    USER     = input("Username: ")
    PASSWORD = getpass.getpass()

def get_dataset_infos():
    # parameters
    infos = {}
    
    # Extract dataset information from cvat server (json-formated string)
    logging.info(f"[DATASET] : Request info from cvat server")
    CMD0=f"python {CVAT_CODE_LOCATION}/cli.py --auth {USER} ls --json"
    stream = pexpect.spawn(CMD0)
    
    stream.expect('Password:')
    stream.sendline(PASSWORD)
    
    stream.expect(pexpect.EOF)

    stdout = stream.before.decode('utf-8')
    stream.wait()
    
    # Debug support
    logging.debug(f"[DATASET] : Answer from cvat server <<{stdout}>>")
    
    # format string to dict
    logging.debug(f"[DATASET] : Parsing answer from cvat server")
    infos = json.loads(stdout)
    return infos

def extract_datasets(infos):
    logging.debug(f"[DATASET] : Parsing answer from cvat server")
    datasets = []
    for i in infos:
        if "project_id" in i and\
            i["project_id"] not in datasets:
            datasets += [i["project_id"]]
    logging.info(f"[DATASET] : The datasets found: <<{datasets}>>")
    return datasets

def generate_labels(gt_file, task_id):
    logging.info(f"[DATASET] : Exporting Labels from Cvat Server of task <<{task_id}>> to {gt_file}")
    CMD1=f"python {CVAT_CODE_LOCATION}/cli.py --auth {USER} dump --format \"MOT 1.1\" {task_id} {gt_file}"
    stream = pexpect.spawn(CMD1)
    stream.expect('Password:')
    stream.sendline(PASSWORD)
    stream.expect(pexpect.EOF)
    stdout = stream.before.decode('utf-8')
    stream.wait()
    
def generate_images(start_frame, end_frame, image_folder, task_id):

    # Check files if already downloaded
    files=list(pathlib.Path(image_folder).iterdir())
    if len(files) > 0 :
        # Figure out, which files need to downloaded...

        # Pattern Matcher
        base_pattern=f"([0-9]+)"
        prog = re.compile(base_pattern)

        # Template list
        frames_to_export=list(range(start_frame, end_frame))
        frames_existing=[]

        # Do check
        for _file in files:
            result = prog.fullmatch(_file.stem)
            if result is not None:
                frames_existing+=[int(result.group(1))]
        
        # Only download files, which were NOT downloaded already
        frames_to_export = [frame for frame in frames_to_export if frame not in frames_existing]
        frames_to_export = [str(i) for i in frames_to_export]
    else:
        # Make full clean download
        # frames_to_export=list(range(start_frame, end_frame))
        frames_to_export=list(range(start_frame, end_frame))
        frames_to_export=[str(i) for i in frames_to_export]

    # Fail-safe if no export required
    if len(frames_to_export) == 0 :
        logging.info("Skipping download. Files already exist.")
        return

    # Convert list to  space separated string
    frames_to_export=" ".join(frames_to_export)

    # Do the actual download of the images
    try:
        logging.debug(f"[DATASET] : Exporting images from Cvat Server of task id to {image_folder}")
        CMD2=f"python {CVAT_CODE_LOCATION}/cli.py --auth {USER} frames --outdir {image_folder} {task_id} " + frames_to_export
        stream = pexpect.spawn(CMD2, timeout=None)
        stream.expect('Password:')
        stream.sendline(PASSWORD)
        stream.expect(pexpect.EOF)
        stdout = stream.before.decode('utf-8')
        stream.wait()
    
    finally:
        # Get Current filenames
        files=list(pathlib.Path(image_folder).iterdir())

        # Rename files to ensure proper format for all videos
        base_pattern=f"task_{task_id}_frame_([0-9]+)"
        prog = re.compile(base_pattern)
        
        for file_name in files:
            result = prog.fullmatch(file_name.stem)
            if result is not None:
                new_file_name = pathlib.Path(file_name.parent, result.group(1) + file_name.suffix)
                file_name.rename(new_file_name)
    

def create_dataset(datasetid, infos, output):
    subsets = ["Train", "Test", "validation"]
    modes   = ["gt", "img1"]            # + ["gt"] gt includes the "groundtruth" files
                                        # + ["det"] det includes the "raw" detections
                                        # + ["img1"] img1 contains the images of the video file. This is pretty space wasting...

    # We want to write images later, because this will take a long time
    # Also we may want to do this smartly
    buffer_for_image_writing = []
    
    # Generate Folder structure for dataset
    logging.info(f"[DATASET] : Processing dataset {datasetid}")
    for i in infos:
        # Extract key information
        assert "name" in i, "Name Key has to be present in task dict"
        name = i["name"]
        
        assert "subset" in i, "Subset Key has to be present in task dict"
        subset = i["subset"]
        
        assert "project_id" in i, "Project_id Key has to be present in task dict"
        dataset = i["project_id"]
        
        assert "id" in i, "Id Key has to be present in task dict"
        task = i["id"]
        
        assert "size" in i, "Size Key has to be present in task dict"
        size = i["size"]

        # Ignore not to dataset relevant tasks
        if datasetid != dataset:
            logging.debug(f"[DATASET] : Task with name <<{name}>> is ignored. Not requested dataset {datasetid} was instead <<{dataset}>>. Ignore.")
            continue;

        # Ensure task is in a defined subset
        if subset not in subsets:
            logging.debug(f"[DATASET] : Task with name <<{name}>> is assigned an unknown subset <<{subset}>>. Ignore.")
            continue;
        
        # Create subfolder
        logging.debug(f"[DATASET] : Create Sample in MOT Format under <<{output}>>")
        folder_path = pathlib.Path(output) / pathlib.Path("dataset_"+str(dataset)) / pathlib.Path(subset) / pathlib.Path(name)
        folder_path.mkdir(parents=True, exist_ok=True)

        # Create data-modes
        for mode in modes:
            mode_path = folder_path / pathlib.Path(mode)
            mode_path.mkdir(parents=True, exist_ok=True)

        # Create gt.txt in /gt
        generate_labels(str(folder_path / pathlib.Path("gt") / pathlib.Path("gt.txt")), task)
        
        # Create seqinfo.ini
        info_file = str(folder_path / pathlib.Path("seqinfo.ini"))
        info_content = "[Sequence]\n"                       +\
                       f"name={name}\n"                     +\
                       f"imDir=img1\n"                      +\
                       f"frameRate=30\n"                    +\
                       f"seqLength={size}\n"                +\
                       f"imWidth=????\n"                    +\
                       f"imHeight=????\n"                   +\
                       f"imExt=.jpg\n"
        with open(info_file, "w") as hdl:
            hdl.write(info_content)

        # Fill our image buffer for later processing

        start_frame  = 0
        end_frame    = int(size)
        image_folder = str(folder_path / pathlib.Path("img1"))
        task_id      = task

        buffer_for_image_writing += [(start_frame, end_frame, image_folder, task_id)]
    
    logging.info("[DATASET] : Exporting Images. This will take a while... ")
    for i in tqdm.tqdm(range(len(buffer_for_image_writing))):
        generate_images(*buffer_for_image_writing[i])
    
    logging.info("[DATASET] : Finished export")
    

if __name__ == "__main__":
    logging.debug(f"[DATASET] : Parsing arguments.")
    args = parse_args()
    
    # Get secret and store to avoid tedious reentering of passwords
    cache_server_password()
    
    # Get Dataset infos (dict obj)
    info = get_dataset_infos()
    
    # Extract datasets
    datasets = extract_datasets(info)

    # Generate ground-truth folder structure
    for dataset in datasets:
        create_dataset(dataset, info, args.output[0])
    

