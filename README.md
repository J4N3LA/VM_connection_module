# WORK IN PROGRESS...
#   vm_connection
#### SSH Script Executor with live output streaming and fail-recovery
This python module lets us execute script on remote host, while streaming the output directly on our terminal.
It uses __'paramiko'__ module for creating SSH tunnel and __'tmux'__ sessions for connection failure recovery. More details usage will be covered below.

## Dependencies
This script was developed inside python __'venv'__ environment. list of required modules was generated using __```pip freeze > requirements.txt```__. You can use this generated file to install all required python modules using __```pip install -r /path/to/requirements.txt```__ command. 

Usually it is recommended to run __```pip install```__ command inside your virtual-environment. Here is a quick guide to set up safe evironment for this script:
```
# Python 3.3+ versions inlude venv by default. Make sure to have related version of python installed.
# To clone this repository, create venv evnironment, isolate your code inside venv, and install dependencies run:

git clone https://github.com/J4N3LA/VM_connection_module.git
cd VM_connection_module
python3 -m venv .
source bin/activate
pip install -r requirements.txt

# After this you are ready to run the vm_connection.py
```
### !!! ***This script can be run against ```RHEL/DEBIAN``` systems. Main requirement is that target  hosts must have ```tmux``` installed.*** !!! 
I assume uptime and sshd will be present :)

---

## Components
### SSHConnection class methods:
- #### `__init__`
     #### SSHConnection class object initialization method. Takes following parameters:
     - port - Remote host's ssh port
     - user - Remote host's username
     - key_path - Rrivate ssh key location for authentication to remote host
     - script_path_local - Location of script to copy and run
     - script_path_remote - Location of where the script will be copied and executed from on remote host
     - local_log_file - location to store script execution logs locally

     #### Example:
        conn = SSHConnection(
                    host="192.168.0.50",
                    port=22,
                    user="devops",
                    key_path="/home/njanelidze/.ssh/id_ed25519",
                    script_path_local=f"./{script_name}",  
                                                            --- 'script_name' is a var set in code
                    script_path_remote=f"/tmp/{script_name}",
                    local_log_file=log_filename,
                    )

- #### `is_alive()`
     ####  Method to check if remote host is alive/sshd service is running Takes following parameters:
     - __retries__ - number of retries before declaring host unreachable
     - __delays__ - delay in seconds between reties
     #### To check if host is alive we use 3 different ways one by one on every retry. At least one of these checks must be ___True___ to return ___True___ from these method otherwise script exits:
     - __ping__ - Send ICMP packet to remote host to check if it is alive. There is high possibility that ICMP packet will be dropeed therefore return value of ___False___ does not mean host is dead.
     - __socket__ - Checks if it is possible to create TCP connection with remote host. Uses socket module and returns ___True/False___ based on the result.
     - __SSH__ - Tries to create single-user ___ssh___ connection and execute  ___whoami___  command remote host. 
     - __Other idea__ - If we use some kind of VM orchestrators (Vsphere,Proxmox...), Best way to check would have been to send request with curl towards its API and parse the recived data for VM state .

     #### Example output of is_alive(2,5) method:
        Trying to connect to 192.168.0.50:22...
        Checking if host machine is active...
        Try 1: Checking connections
            Ping check status: False
            Socket  check status: False
            SSH connection check status: False
        Try 2: Checking connections
            Ping check status: False
            Socket  check status: False
            SSH connection check status: False
        Could not connect to 192.168.0.50:22. Error: Host 192.168.0.50 on port 22 is unreachable after multiple retries.






- #### `connect()`
- #### `reconnect()`
- #### `upload_script()`
- #### `execute()`
- #### `execute_after_reconnect()`
- #### `close()`
### other:
- #### `log_output_line()`


# WORK IN PROGRESS...

