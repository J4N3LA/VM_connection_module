#   vm_connection
## SSH Script Executor with live output streaming and fail-recovery
#### This python module lets us execute script on remote host, while streaming the output directly on our terminal.
#### It uses __'paramiko'__ module for creating SSH tunnel and __'tmux'__ sessions for connection failure recovery. Idea is to first upload script to remote host with sftp, than execute this script inside __'tmux'__ session, As soon as script produces stdout/stderr output we are receiveing it via paramiko'c ssh channels, filtering it from unwanted characters (terminal ANSI codes,newlines, tmux statusbars...) and passing filtered "data" to a callback function, which by itself prints it to our terminal and logs it inside local timestamped log file.
#### Also main feature is to also recover our streaming process, for example when loosing network connection to remote  vm. This is also accomplished with the help of 'tmux' sessions. The initial command that ran our script inside tmux is independent from ssh session, meaning if our ssh channel goes down - script will continue running, and after we reconnect automatically we re-attach to the same 'tmux' session.
#### This was the core idea of this module,  More detailes of each component will be covered below.


##### !!! ***There is a small bug when initial start of streaming. first 4-6 lines of output gets duplicated, I think that is becasue of tmux's startup/intialization process. I think starting tmux session independently and then run command inside it will clean things up*** !!!

---
## Dependencies & requirements
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
```
Since this module only uses key-based ssh authentication to remote hosts. It is required to have you user's public ssh-keys distributed to remote host.
```
# if you dont have ssh key-pair. First run 'ssh-keygen' command and fill it's prompts.

ssh-keygen

# After running 'ssh-keygen' command, you will need to copy generated public key (ending with .pub) to remote host
# For this you can use 'ssh-copy-id'. This command will require remote  user's password for the first time.

ssh-copy-id -i /path/to/generated/key.pub remote_host_user@remote_host_ip

# After this you should be able to directly authenticate to remote host's ssh-agent using

ssh remote_host_user@remote_host_ip

# If prompted for 'Are you sure you want to continue connecting (yes/no)?' type yes
```
Main component that makes this script work is ```tmux```, so make sure to install it on remote hosts
```
sudo dnf install tmux -y       # RHEL/CentOS
sudo apt install tmux -y       # Ubuntu/Debian
```


---

## Components:
### SSHConnection class methods:
- ### `__init__`
     #### SSHConnection class object initialization method. Takes following parameters:
     - port - Remote host's ssh port
     - user - Remote host's username
     - key_path - Rrivate ssh key location for authentication to remote host
     - script_path_local - Location of script to copy and run (full path)
     - script_path_remote - Location of where the script will be copied and executed from on remote host (full path)
     - local_log_file - location to store script execution logs locally  <---- hardcoded inside main portion (planning to change)

     #### Example:
        conn = SSHConnection(
                    host="192.168.0.50",
                    port=22,
                    user="devops",
                    key_path="/home/njanelidze/.ssh/id_ed25519",
                    script_path_local="/path/to/script",  
                    script_path_remote=f"/path/to/script",
                    local_log_file=log_filename,
                    )
#
- ### `is_alive()`
    ####  Method to check if remote host is alive/sshd service is running. Used by ```connect()``` method. Takes following parameters:
     - __retries__ - number of retries before declaring host unreachable
     - __delays__ - delay in seconds between reties
     #### To check if host is alive we use 3 different ways one by one on every retry. At least one of these checks must be ___True___ to return ___True___ from these method otherwise script exits:
     - __ping__ - Send ICMP packet to remote host to check if it is alive. There is high possibility that ICMP packet will be dropeed therefore return value of ___False___ does not mean host is dead.
     - __socket__ - Checks if it is possible to create TCP connection to remote host. Uses socket module and returns ___True/False___ based on the result.
     - __SSH__ - Tries to create single-use ___ssh___ connection and execute  ___whoami___  command remote host.

     - __Other idea__ - If we use some kind of VM orchestrators (Vsphere,Proxmox...), Best way to check would have been to send request with for example ```requests``` module  towards its API and parse the recived data for VM state .

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
#
- ### `connect()`
    #### This method is responsible for creating Paramiko SSH connection to remove host. It uses ```is_alive()``` method at the beggining to check if remote host is active. It only takes ___timeout___ parameter, which is used for Paramikos connection configuration. snippet of ```connect()``` method
    ```
        try:
            self.client = paramiko.SSHClient()
            self.client.load_system_host_keys()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(hostname=self.host,
                                port=self.port,
                                username=self.user,
                                key_filename=self.key_path,
                                timeout=timeout,
                                allow_agent=False,
                                look_for_keys=False,
                                password=None
                                )
            print("Connection successfull.")
            return True
    ```
#
- ### `reconnect()`
    #### This method is used to for reconnection to remote host. It repeatedly reuses ```connect()``` method. Used inside ```execute_after_reconnect()``` method. Sets ```self.boot_after``` if ```connect``` is successfull which is later used for boot detection logging . Raises ```HostUnreachable``` exception if failed. Takes following parameters:
    - __retries__ - number of retries to execute ```connect()``` method
    - __delays__ - delay period between each retry
    
    ```
        for _ in range(retries):
            if self.connect(60):
                self.boot_after = self.get_boot()
                return True
            time.sleep(delay)
        raise HostUnreachable("All reconnection attemtps failed")
    ```
#
- ### `upload_script()`
    #### This method is used to upload script to remote host which will later be executed inside ___tmux___ session. Raises exception if file upload was unsussessfule and exits the program. It uses ___paramiko___'s sftp client to accomplish this goal. Heres a snippet of this method:
    ```
        def upload_script(self):
        try:
            sftp = self.client.open_sftp()
            sftp.put(self.script_path_local, self.script_path_remote)
            sftp.close()
            _,_,stderr = self.client.exec_command(f"chmod +x {self.script_path_remote}")
    ```
#
- ### `execute()`
    #### This is the method that is responsible for executing the script on remote host inside ___tmux___ session. After connection is established with ```connect()``` method, it opens up a channel where actual data flow is occuring. It takes following parameters:
    - __log_output_line__ - callback function that is responsible for printing recived data to our terminal and writing to a log file
    - __timeout__ - sets the time limit of streaming while no data is being recieved (command is hung on remote host)
    - __f__ - file object identificator that is used for local logging of recieved stream

    #### Creating data channel and executing command on remote host inside new tmux session for further proccessing:
    ```
        def execute(self,log_output_line,timeout,f):
            transport_name = self.client.get_transport()
            channel = transport_name.open_session()
            channel.get_pty()
            self.boot_before = self.get_boot()

            channel.exec_command(f"tmux new -s script_execution 'tmux set-option -g status off; {self.script_path_remote}'")
    ```

    ### Streaming:
    #### recieved data from channel is stored inside ```data_stdout``` string, and continiously processed to be seperated by "newline" characters using split("\n",1). Splitted characters are stored inside ```line```(first portion of split) and the remaining portion as ```data_stdout``` string (remaining portion updates the original string). 
    #### Each iteration of data splitting loop calls ```log_output_line(line,f)``` function, where ```line``` is the data that is sent for printing in our terminal and ```f``` is opened file object identificator which is used for logging the output locally.
    #### Here is the snippet of ```execute()``` method that is responsible for streaming and logging the output line by line:

    ``` 
        while channel.recv_ready():
            data_stdout += channel.recv(1024).decode()
                while "\n" in data_stdout:
                    line, data_stdout = data_stdout.split("\n",1)
                    log_output_line(line,f)
                    last_activity = time.time()
    ```
    
    ### Timeout monitoring:
    #### This method also monitors timeout parameter. for each iteration of loop mention above, we also update ```last_activity``` variable with current time value. If no data is recived ("\n" not in data_stdout) , we get out of the streaming loop and reach this condition check:
    ```
        if time.time() - last_activity >= timeout:
            print("Time exceeded. exiting...")
            return -5
    ```
    #### This condition will be continously checked because of outer while loop and ```execute()``` method will be exited if met. 


    ### Ending or Restarting streaming process on connection loss:
    #### To identify ending of script execution on remote host we check channel's ```exit_status_ready``` and ```recieve_ready``` parameters.
    #### if ```exit_status_ready``` value is non-zero, this means that paramiko's SSH connection was disturbed most likely by loosing connection to remote host. In such case ```ConnectionError``` exception is raised and caught by ```excecute``` method's exception, which itself calles ```execute_after_reconnect()``` method. Otherwise method is exited.

    ```
        if channel.exit_status_ready() and not  channel.recv_ready():
            exit_code = channel.recv_exit_status()
            if exit_code != 0:
                raise ConnectionError("SSH connection lost before command finished")
            else:
                print(f"Channel streaming completed, to review output/errors please read: {self.local_log_file}")
                break
    ```

#
- ### `execute_after_reconnect()`
    #### This method is used for reconnecting and resuming the streaming process after we loose connection to remote host. It is called once from ```execute()``` method's exception, and called recursively from itself for future connection failures. It is similar to ```execute()``` method and takes same parameters, however there are some key components that make it special:
    
    ### Reboot detection:
    #### When exception of ```exceute()``` method calls this method, we first check if loss of connection was caused by host's reboot or not, we are checking this because reboot would have caused the initial script process to dissapear, which means we must re-run the script on remote host by re-executing this program.
    #### Reboot detection is done by this conditional check inside this method:
    ```
            if self.boot_before < self.boot_after:
                log_output_line("\nALERT: ====REBOOT DETECTED====\n", f)
                raise RebootNotify("====REBOOT DETECTED====") 
    ``` 
    #### This conditional checks values of ```boot_before``` and ```boot_after``` which are generated by  method called ```get_boot``` (This method will be discussed below). 
    #### If it detects that initinal boot marker - ```boot_before``` (set when calling ```execute()``` method) is different/less that the next boot marker - ```boot_after``` (set when calling ```reconnect()```, it logs reboot notifier messege in the log file and will raise ```RebootNotify``` exception to exit the program.

    ### Command output stream recovery:
    #### Another difference is the command that is executed on remote host. If no reboot was detected  , this means that our initial ```tmux``` session still exists in the backgroud. This lets us to continue receiving original stream data. 
    #### Compared to ```execute()``` method's ```channel.exec_command(f"tmux new  -A -s script_execution 'tmux set-option -g status off; {self.script_path_remote}'")```, we are not creating new tmux session with our script output, we are  re-attaching to the already existing one, identified by it's name ```(-t)```  using this command:
    ```
        channel.exec_command(f"tmux attach-session -t script_execution")
    ```
    #### In case of further connection losses, ```execute_after_reconnect``` recursively calls itself and reconnects to the host, Thus giving use continious data streaming.
    #### Other than these it's identical to ```execute()``` method.




#
- ### `get_boot()`
    #### This method is used to retrive remote systems's intial boot time. This is accomplished by running ```uptime -s``` command on remote hosts, an returning the value to the caller. 

    ```
        _,stdout,_ = self.client.exec_command(f"uptime -s")
        boot = stdout.read().decode().strip()
        boot_time = datetime.strptime(boot, "%Y-%m-%d %H:%M:%S")
        return boot_time`
    ```
    #### Currently this method is used inside ```execute()``` and ```reconnect()``` methods, to set ```boot_before``` and ```boot_after``` class variable values.
    #
- ### `close()`
    #### This method simply clodes ```paramiko``` SSH client instance 
___
## Callback function for printing and logging:
- #### `log_output_line()` - This function is responsible for printing recived data from the remote host's script output to our terminal, as well as logging this data to a local log file.
    #### It called from ```execute()``` and ```execute_after_reconnect()``` methdos. Thiese methods pass data as ```line``` argument to this function. After recieving, the data is filtered by removing ANSI symbols and tmux status bars (A little bit buggy for now :) ) .
    #### After filtration data is passed into print statement for us to see and write() method for local logging.


```
    def log_output_line(line,f):
        clean_line = ANSI_ESCAPE.sub('',line).strip()
        if clean_line and not clean_line.startswith("[script_ex0:tmux") and not clean_line.startswith('10;?11;?') and not clean_line.startswith('[script_ex0:bash*'):
            print(f"[REMOTE] >> {clean_line}")
            f.write(clean_line + "\n")
```
## Unit testing using pytest and pytest-mock
#### Since it is required to perform tests on the project. I created ```test_vm_connection.py``` file, that includes test for different units of the ```vm_connection.py``` file.
#### Unit test are performed using pytest module. The simulation of resonses is performed by pytest-mock module.

####  I created fixture SSHConnection object ```class_object```, that will be used further passed in testing functions. 
#### Beside this  ```test_vm_connection.py``` inlude tests for:
- ### __Connecting to remote host__ - test_connection()
     Mocked ```is_alive``` method so it always return True. 
    ```
        mocker.patch.object(class_object,"is_alive",return_value=True)
    ```
     Mocked paramiko ```SSHClient``` object
    ```
        mock_client = mocker.Mock()
        mocker.patch("paramiko.SSHClient", return_value=mock_client)
    ```
    #### Finally I am asserting ```connect()``` method to simulate connection process and retrive value

- ### Reconnecting to remote host - test_reconnect_success()
    Since ```Reconnect()``` method uses ```connect()``` method for fixed number of times, I simulated two fake return values ___False___ and then ___True___ from ```connect``` method to check it's behavior on first failure:
    ```
    mocker.patch.object(class_object, "connect", side_effect=[False, True])
    ```
    The ```get_boot()``` method is useless in this case so I am faking it's return as ___None___
    ```
    mocker.patch.object(class_object,"get_boot",return_value=None)
    ```
    Finally I am asserting return result of ```reconnect(2,0)```

- ### Failed reconnecting exception test - test_reconnect_failure()
    In our original code ```reconnect``` method raises exception if all ```connect()``` calls fails. So we are simluating that exception is raised on all ```connect()``` failures
    ```
    # Mock return values of connect() and get_boot()
    mocker.patch.object(class_object, "connect", return_value=False)
    mocker.patch.object(class_object, "get_boot", return_value=None)

    #Simulate exception raise
    with pytest.raises(HostUnreachable) as check_value:
        class_object.reconnect(retries=2, delay=0)

    # Check exception message
    assert "All reconnection attemtps failed" in str(check_value.value)
    ```

- ### Test execute data logging - test_execute()
    For this test we are testing if recived data from SSH channel is handled correctly. First we are "disabling" ```execute_after_reconnect()``` and ```get_boot()``` methods.
    ```
    mocker.patch.object(class_object,"get_boot",return_value = None)
    mocker.patch.object(class_object, "execute_after_reconnect", return_value=None)
    ```
    After that we are mocking paramiko's channel methods
    ```
    mock_channel = mocker.Mock()
    mock_channel.recv_ready.side_effect = [True,False]     
    mock_channel.recv.side_effect = [b'line1\nline2\nline3\nline4\n']   < -------- Faking recived data
    mock_channel.exit_status_ready.side_effect = [False,True] 
    mock_channel.recv_exit_status.return_value = 0

    mock_transport = mocker.Mock()
    mock_transport.open_session.return_value = mock_channel

    class_object.client = mocker.Mock()
    class_object.client.get_transport.return_value = mock_transport
    ```
    Next we are creating list ```mock_data_stdout = []``` to capture lines passed from callback function string. And also creating fake callback method 
    ```
        mock_data_stdout = []
        def mock_logging(line,f):
            mock_data_stdout.append(line)
    ```
    Finally calling the ```execute()``` method and checking if all data is present 
    ```
        class_object.execute(mock_logging,timeout=5,f=None)

        assert "line1" in mock_data_stdout
        assert "line2" in mock_data_stdout
        assert "line3" in mock_data_stdout
        assert "line4" in mock_data_stdout
    ```

- ### Simulate timeout for execute method - test_command_exec_timeout()
    In this test we are testing timeout coditional that is present in our original ```execute()``` method. Since original declares timeout if current_time - last_activity > timeout and should exit the method with return value of -5. To achive this we must once again simulate SSH client, and channel methods with no data flow in them, Which can be accomplished by setting channel's readiness status to always __False__ and check return value.
    ```
    mock_channel = mocker.Mock()
    mock_channel.recv_ready.return_value = False 
    mock_channel.exit_status_ready.return_value = False
    mock_channel.recv_exit_status.return_value = 0
    ```
    After mocking all relevant processes we call ```execute()``` with custome timeout value and assert its return value
    ```
        result = class_object.execute(mock_logging, timeout=1, f=None)
        assert result == -5
    ```

- ### Simulating network drop to check reconnection function activation - test_execute_network_drop()
    For this test we are deliberately raising exception inside ```execute()``` method's __try:__ block so that the __exception__ block calls ```reconnect_after_execute()``` method. We accomplish this by creating mock exception function and assigning it to ```client.recv_ready()```'s mock ```mock_channel.recv_ready```

    ```
        def recv_ready_side_effect():
            raise Exception("netw drop")  
        mock_channel.recv_ready.side_effect = recv_ready_side_effect
    ```
    Also this we are "disabling" actual execution output of ```execute_after_reconnect()``` method, Because We only need to check if it was called.
    ```
    execute_after_mock = mocker.patch.object(class_object, "execute_after_reconnect", return_value=None)
    ```
    finally after "disabling" unneeded paramiko class methods, we pass mock callback function into fake ```execute()``` method and check if fake ```execute_after_reconnect```(```execute_after_mock```) was called or not.
    ```
        def mock_logging(line, f):
            mock_data_stdout.append(line)

        class_object.execute(mock_logging, timeout=1, f=None)

        assert execute_after_mock.called
    ```

- ### Test for reboot exception - test_reboot_notify_exception()
    In this test we are checking if ```RebootNotify``` exception is called. To do this we are manually setting ```boot_before``` and ```boot_after``` values:
    ```
        class_object.boot_before = datetime.strptime("2025-08-13 10:00:00", "%Y-%m-%d %H:%M:%S")
        class_object.boot_after  = datetime.strptime("2026-08-13 10:00:00", "%Y-%m-%d %H:%M:%S")
    ```
    mocking return value of ```reconnect()``` to ```True``` and checking if execution of ```reboot_after_notify()``` method raises and ```RebootNotify exception.
    ```
        mocker.patch.object(class_object, "reconnect", return_value=True)

        with pytest.raises(RebootNotify):
            class_object.execute_after_reconnect(mock_logging, timeout=5, f=None)
    ```



