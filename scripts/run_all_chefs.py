import glob
import json
import os
import subprocess
import time

from signal import signal, SIGINT
from sys import argv, exit

# assumes the script is being run from a directory with all chefs in a chefs subdirectory.
# To get the repos, do `mkdir chefs; cd chefs; fab clone_chef_repos`
orig_root = os.getcwd()
succeeded = []
failed = []

# This should be removed once the script has done a complete run with the other chefs.
huge_chefs = [
    'sushi-chef-khan-academy',
]

broken_chefs = [
    'sushi-chef-noktta', # requirements file not found
    'sushi-chef-storybooks-minnesota', # requirements file not found, relies on code not in repo
]

needs_creds_chefs = [
    'sushi-chef-shls',
    'sushi-chef-sikana', 
    'sushi-chef-teded', 
]

# depends on manually added files
needs_assets_chefs = [
    'sushi-chef-profuturo',
    'sushi-chef-tictaclearn',
]

empty_chefs = [
    'sushi-chef-proyecto-biosfera',
    'sushi-chef-skoool', # not implemented
    'sushi-chef-stop-it-at-the-start', # no longer used
    'sushi-chef-women-talk-money', # never actually started, done manually
    'sushi-chef-world-digital-library' # never started
]

chefs_to_skip = huge_chefs + needs_creds_chefs + needs_assets_chefs + empty_chefs


run_logs = {}
logs_file = os.path.abspath(os.path.join('chefs', 'run_logs.json'))
if os.path.exists(logs_file):
    run_logs = json.load(open(logs_file))


def save_run_logs():
    print("Saving run logs to {}...".format(logs_file))
    with open(logs_file, 'w') as f:
        f.write(json.dumps(run_logs, indent=4))
    
    
def print_logs():
    num_succeeded = 0
    for subdir in run_logs:
        if run_logs[subdir]['succeeded']:
            num_succeeded += 1
        print("{}: {}".format(subdir, run_logs[subdir]['succeeded']))
        if 'errors' in run_logs[subdir]:
            last_20 = '\n'.join(run_logs[subdir]['errors'].split('\n')[-20:])
            print(last_20)
            
    print("Total runs: {}".format(len(run_logs)))
    print("Successful runs: {}".format(num_succeeded))
    

if '--print' in argv:
    print_logs()
    exit(0)


def signal_handler(signal_received, frame):
    # Handle any cleanup here
    os.chdir(orig_root)

    exit(1)

signal(SIGINT, signal_handler)

counter = 0
os.chdir('chefs')
chefdirs = os.listdir('.')
chefdirs.sort()

for subdir in chefdirs:
    # we've already run, don't try to run again.
    succeeded = False
    if subdir in run_logs:
        if not 'has_requirements' in run_logs[subdir]:
            run_logs[subdir]['has_requirements'] = os.path.exists(os.path.join(subdir, 'requirements.txt'))
            save_run_logs()
        succeeded = run_logs[subdir]['succeeded']
    
    if succeeded or not subdir.startswith('sushi-chef') or subdir in chefs_to_skip:
        print("Skipping {}".format(subdir))
        if subdir in run_logs:
            del run_logs[subdir]
            save_run_logs()
        continue
    print("Processing {}".format(subdir))
    os.chdir(subdir)
    print("Running {}".format(subdir))
    
    # this is a little trick, pipenv will use this directory
    # if it exists. This way we don't clutter the system
    # venv directory with these.
    os.makedirs('.venv', exist_ok=True)
    status = 0
    has_requirements = False
    # we are using pipenv only for the simplified environment management, not the dependency management.
    if os.path.exists('requirements.txt'):
        result = subprocess.run(['pipenv', 'install', '--skip-lock', '-r', 'requirements.txt'], stdout=None, stderr=None)
        status = result.returncode
        has_requirements = True
        
    if status == 0:
        result = subprocess.run(['pipenv', 'run', 'pip', 'install', '-e', '/Users/kevino/code/LearningEquality/ricecooker'], stdout=None, stderr=None)
        status = result.returncode
    if status == 0:
        # This is not a hard ricecooker dependency since many sources don't need it.
        result = subprocess.run(['pipenv', 'run', 'pip', 'install', 'pyppeteer'], stdout=None, stderr=None)
        status = result.returncode
    if status == 0:
        # The version of GitPython included by many repos is now broken, so just always update it.
        result = subprocess.run(['pipenv', 'run', 'pip', 'install', '-U', 'GitPython'], stdout=None, stderr=None)
        status = result.returncode
    if status != 0:
        print("Failed to install dependencies for {}...".format(subdir))

    start = time.time()
    errors = ''
    if status == 0:
        scripts = glob.glob("*chef.py")
        if len(scripts) == 1:
            script = scripts[0]
            try:
                cmd = ['pipenv', 'run', 'python', script, 'dryrun']
                if  subdir in run_logs and 'args' in run_logs[subdir]:
                    cmd.extend(run_logs[subdir]['args'])
                subprocess.run(cmd,  check=True, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as e:
                print("Error occurred")
                status = 1
                errors = e.stderr.decode('utf-8')
        else:
            status = 1
            print("Unable to find chef script for {}.".format(subdir))
    os.chdir('..')
    elapsed = time.time() - start
    run_logs[subdir] = {
                        'succeeded': status == 0,
                        'elapsed': elapsed,
                        'has_requirements': has_requirements
                        }
    if not status == 0:
        run_logs[subdir]['errors'] = errors
    save_run_logs()

    counter += 1
    print("Counter is now {}".format(counter))


os.chdir(orig_root)
save_run_logs()


