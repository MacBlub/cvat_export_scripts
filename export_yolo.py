#!/bin/python
# This a linux script! No windows formatted paths yet supported...

import re
import os
import json
import tqdm
import shutil
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
s
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

def download_zip(task_id, target_file):
    CMD1=f"python {CVAT_CODE_LOCATION}/cli.py --auth {USER} dump --format \"YOLO 1.1\" {task_id} {target_file}"
    stream = pexpect.spawn(CMD1)
    stream.expect('Password:')
    stream.sendline(PASSWORD)
    stream.expect(pexpect.EOF)
    stdout = stream.before.decode('utf-8')
    stream.wait()
 

def generate_labels(name, sub_set, task_id, gt_folder):
    logging.info(f"[DATASET] : Exporting Labels from Cvat Server of task <<{task_id}>> to {gt_folder}")
    
    # Get clean tmp folder
    logging.info(f"[DATASET] : Create tmp Folder")
    tmp_dir = pathlib.Path("/tmp/DEBUGGING_FOLDER")
    if tmp_dir.exists():
        logging.debug("[DATASET] : Folder already exists. Delete!")
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir()
    tmp_file = tmp_dir / pathlib.Path("export.zip")
    
    # First download zip file
    logging.info(f"[DATASET] : Download ZIP")
    download_zip(task_id, str(tmp_file))
    
    # unzip zip file
    logging.info(f"[DATASET] : Unzip GT")
    export_dir = tmp_dir / pathlib.Path('exported')
    CMD1=f"unzip -d {str(export_dir)} {str(tmp_file)}"
    stream = pexpect.spawn(CMD1)
    stream.expect(pexpect.EOF)
    stream.wait()
    
    # Ensure target folder exists
    (gt_folder / pathlib.Path("labels")).mkdir(exist_ok=True, parents=True)

    # for each label_file in obj_subset_data
    # export_dir / obj_{subset}_data
    label_files = []
    label_dir   = export_dir / pathlib.Path(f"obj_train_data")
    for filegt in label_dir.iterdir():

        # Filter directories
        if filegt.is_dir():
            logging.debug(f"{filegt} is directory. Ignoreing.")
            continue;
        
        # generate_new_label_name
        new_filename = f"task_{task_id}_{filegt.name}"
        new_file     = gt_folder / pathlib.Path("labels") / pathlib.Path(new_filename)

        # Copy & rename files
        logging.info(f"[DATASET] : Copy from {str(filegt)} to {str(new_file)}")
        shutil.copyfile(filegt, new_file)

        # Save filename for train.txt
        label_files += [pathlib.Path(new_filename)]

    # Append filename to "split".txt all new relative paths
    with open(str( gt_folder / pathlib.Path(str(sub_set.lower())+".txt") ), "a") as hdl:
        for label in label_files:
            hdl.write(f"{str(label)}\n")

def generate_images(start_frame, end_frame, _image_folder, task_id):
    # Ensure target folder exists
    image_folder = _image_folder / pathlib.Path("images")
    image_folder.mkdir(exist_ok=True, parents=True)

    # Check files if already downloaded
    files=list(pathlib.Path(image_folder).iterdir())
    if len(files) > 0 :
        # Figure out, which files need to downloaded...

        # Pattern Matcher
        base_pattern=f"task_{task_id}_frame_([0-9]+)"
        prog = re.compile(base_pattern)

        # Template list
        ## Choosing 30 frames
        #step = (end_frame - start_frame) / 30
        #frames_choosen=[]
        #for x in range(0, 30):
        #    frames_choosen.append(start_frame + x * step)
        ##
        
        frames_to_export=list(range(start_frame, end_frame))
        # frames_to_export = frames_choosen
        frames_existing  = []

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
        frames_to_export=list(range(start_frame, end_frame))
        # frames_to_export= frames_choosen
        frames_to_export=[str(i) for i in frames_to_export]

    # Fail-safe if no export required
    if len(frames_to_export) == 0 :
        logging.info("Skipping download. Files already exist.")
        return
    else:
        logging.info(f"Exporting {len(frames_to_export)} frames...")

    # Convert list to  space separated string
    frames_to_export=" ".join(frames_to_export)

    # Do the actual download of the images
    logging.debug(f"[DATASET] : Exporting images from Cvat Server of task id to {image_folder}")
    CMD2=f"python {CVAT_CODE_LOCATION}/cli.py --auth {USER} frames --outdir {image_folder} {task_id} " + frames_to_export
    stream = pexpect.spawn(CMD2, timeout=None)
    stream.expect('Password:')
    stream.sendline(PASSWORD)
    stream.expect(pexpect.EOF)
    stdout = stream.before.decode('utf-8')
    stream.wait()


def create_dataset(datasetid, infos, output):
    subsets = ["Train", "Test", "Validation"]

    # Create root folder
    logging.debug(f"[DATASET] : Create dataset in yolo Format under <<{output}>>")
    folder_path = pathlib.Path(output) / pathlib.Path("dataset_"+str(datasetid))
    folder_path.mkdir(parents=True, exist_ok=True)

    # Creating dataset.yml
    with open(str(pathlib.Path(output) / pathlib.Path(f"dataset{datasetid}.yaml")), "w") as hdl:
        root_dir  = str(folder_path)
        train_dir = str(folder_path / pathlib.Path("train.txt"))
        val_dir   = str(folder_path / pathlib.Path("validation.txt"))
        test_dir  = str(folder_path / pathlib.Path("test.txt"))

        # Path information based on root_dir
        hdl.write("# Basic information\n")
        hdl.write(f"path: {root_dir}\n")
        hdl.write(f"train: {train_dir}\n")
        hdl.write(f"validation: {val_dir}\n")
        hdl.write(f"test: {test_dir}\n")
        hdl.write("\n")

        # We hardcode the classes for now...
        hdl.write("# Classes \n")
        hdl.write("names:\n")
        hdl.write("    <id>: <some-string>\n")
        hdl.write("\n")

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
        
        # Create gt.txt in /gt
        generate_labels(name, subset, task, str(folder_path))
        
        # Fill our image buffer for later processing
        start_frame  = 0
        end_frame    = int(size)
        image_folder = str(folder_path)
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
    for dataset in reversed(datasets):
        create_dataset(dataset, info, args.output[0])
    

