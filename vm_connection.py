import paramiko
import subprocess
import socket
from datetime import datetime
import time
import re
import sys


class RebootNotify(Exception):
    def __init__(self, message):
        self.message = message

class HostUnreachable(Exception):
    def __init__(self, message):
        self.message = message

class SSHConnection:
    def __init__(self,host,port, user, key_path, script_path_local,script_path_remote,local_log_file):
        self.host = host
        self.port = port
        self.user = user
        self.key_path = key_path
        self.boot_after = None
        self.boot_before = None
        self.script_path_local = script_path_local
        self.script_path_remote = script_path_remote
        self.local_log_file = local_log_file

    def get_boot(self):
        _,stdout,_ = self.client.exec_command(f"uptime -s")
        boot = stdout.read().decode().strip()
        boot_time = datetime.strptime(boot, "%Y-%m-%d %H:%M:%S")
        return boot_time

    def connect(self,timeout):
        print(f"Trying to connect to {self.host}:{self.port}...")
        try:
            if not self.is_alive(2,5):
                print(f"Could not connect to {self.host}:{self.port}.")
                return False
        except HostUnreachable as e:
            print(f"Could not connect to {self.host}:{self.port}. Error: {e}")
            # return False
        
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
        
        except paramiko.AuthenticationException:
            raise HostUnreachable("AUthentication failed")
        except paramiko.SSHException as e:
            raise  HostUnreachable(f"SSH protocl failed.\nError: {e}")
        except Exception as e:
            raise HostUnreachable(f"Could not connect to host:\nError: {e}")
                                  
        
    def reconnect(self,retries,delay):
        for _ in range(retries):
            if self.connect(60):
                self.boot_after = self.get_boot()
                # self.boot_after = datetime.strptime("2026-08-11 12:40:30","%Y-%m-%d %H:%M:%S")
                return True
            time.sleep(delay)
        raise HostUnreachable("All reconnection attemtps failed")
                    

    def is_alive(self,retries,delay):
        print("Checking if host machine is active...")
        for i in range (1,retries+1):
            ping_check = False
            socket_check = False
            ssh_check = False
            print(f"Try {i}: Checking connections")

            if subprocess.run(["ping", "-c", "3", self.host],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL).returncode == 0:
                ping_check = True
                print(f"    Ping check status: {ping_check}")
            else: print(f"    Ping check status: {ping_check}")

            try:
                with socket.create_connection((self.host,self.port),timeout=3):
                    socket_check = True
                    print(f"    Socket  check status: {socket_check}")
            except Exception:
                    print(f"    Socket  check status: {socket_check}")
                    socket_check = False

            if subprocess.run(["ssh", "-o", "BatchMode=yes","-i", self.key_path,"-o", "ConnectTimeout=10", f"{self.user}@{self.host}", "-p", str(self.port), "whoami"],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL).returncode == 0: 
                ssh_check = True
                print(f"    SSH  check status: {ssh_check}")
            else: print(f"    SSH  check status: {ssh_check}")

            

            if ping_check or socket_check or ssh_check: 
                print(f"Host {self.host} on port {self.port} is active.")
                return True
            else: 
                time.sleep(delay)
            
        raise HostUnreachable(f"Host {self.host} on port {self.port} is unreachable after multiple retries.")


    def upload_script(self):
        try:
            sftp = self.client.open_sftp()
            sftp.put(self.script_path_local, self.script_path_remote)
            sftp.close()
            _,_,stderr = self.client.exec_command(f"chmod +x {self.script_path_remote}")
            error = stderr.read().decode().strip()
            if error:
                raise PermissionError("chmod +x failed. Check if file was uploaded")
            else:
                print(f"Script: {self.script_path_local} uploaded to {self.host}:{self.script_path_remote}")
        except Exception as e:
            print(f"Error occured during file upload: {e}")
            sys.exit(1)
        
        
    def execute(self,log_output_line,timeout,f):
        transport_name = self.client.get_transport()
        channel = transport_name.open_session()
        channel.get_pty()
        self.boot_before = self.get_boot()
        print("File open for loggin...")
        print("Starting process as Tmux session...")
        channel.exec_command(f"tmux new  -A -s script_execution 'tmux set-option -g status off; {self.script_path_remote}'")
        # channel.exec_command(f"sleep 100")

        last_activity  = time.time()
        data_stdout = ""
        try:
            while True:
                while channel.recv_ready():
                    data_stdout += channel.recv(1024).decode()
                    while "\n" in data_stdout:
                        line, data_stdout = data_stdout.split("\n",1)
                        # if line.strip():
                        log_output_line(line,f)
                        last_activity = time.time()

                if time.time() - last_activity >= timeout:
                    print("Time exceeded. exiting...")
                    return -5
                
                if channel.exit_status_ready() and not  channel.recv_ready() and not channel.recv_stderr_ready():
                # if channel.exit_status_ready() and not  channel.recv_ready():

                    exit_code = channel.recv_exit_status()
                    if exit_code != 0:
                        raise ConnectionError("SSH connection lost before command finished")
                    else:
                        print(f"Channel streaming completed, to review output/errors please read: {self.local_log_file}")
                        break
                time.sleep(0.1)
        except RebootNotify:
            raise
        except Exception as e:
            print(f"Error during streaming / Connection lost:{e}\n")
            return self.execute_after_reconnect(log_output_line,timeout,f)

    def execute_after_reconnect(self,log_output_line,timeout,f):
        try:
            if not self.reconnect(3,5):
                print("Reconnection attempts failed")
                return -10
        except HostUnreachable as e:
            print(f"Reconnect failed: {e}")
            return -10
        

        if self.boot_before < self.boot_after:
            log_output_line("\nALERT: ====REBOOT DETECTED====\n", f)
            raise RebootNotify("====REBOOT DETECTED====")  
        
        
        reconnected_transport_name = self.client.get_transport()
        channel = reconnected_transport_name.open_session()
        channel.get_pty()
        channel.exec_command(f"tmux attach-session -t script_execution")

        last_activity  = time.time()
        data_stdout = ""
        log_output_line(f"--- Reconnected at {datetime.now().strptime("2026-08-11 12:40:30","%Y-%m-%d %H:%M:%S")} ---",f)
        print("Connection restored to 'Tmux' session. streaming the output...")
        
        try:
            while True:
                while channel.recv_ready():
                    data_stdout += channel.recv(1024).decode()
                    while "\n" in data_stdout:
                        line, data_stdout = data_stdout.split("\n",1)
                        log_output_line(line,f)
                        last_activity = time.time()

                if time.time() - last_activity >= timeout:
                    print("Time exceeded. exiting...")
                    return -5
                
                if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                    exit_code = channel.recv_exit_status()
                    if exit_code != 0:
                        raise ConnectionError("SSH connection lost before command finished")
                    else:
                        print(exit_code)
                        print(f"Channel streaming completed, to review output/errors please read: {self.local_log_file}")
                        break
                time.sleep(0.1)

        except Exception as e:
            print(f"Error during streaming / Connection lost:{e}\nTo review streaming logs please read: {self.local_log_file}")
            return self.execute_after_reconnect(log_output_line,timeout,f)
            

    def close(self):
        if hasattr(self, 'client'):
            self.client.close()
        else:
            print("No active client to close.")


if __name__ == "__main__":

    def log_output_line(line,f):
        clean_line = ANSI_ESCAPE.sub('',line).strip()
        if clean_line and not clean_line.startswith("[script_ex0:tmux") and not clean_line.startswith('10;?11;?') and not clean_line.startswith('[script_ex0:bash*'):
            print(f"[REMOTE] >> {clean_line}")
            f.write(clean_line + "\n")

    script_name = "script.sh"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    log_filename = f"/tmp/{script_name}_{timestamp}.log"
    ANSI_ESCAPE = re.compile(r'''
                    \x1B    
                    (?:     
                        [@-Z\\-_]
                    |       
                        \[
                        [0-?]*  
                        [ -/]*  
                        [@-~]   
                    )
                    ''', re.VERBOSE)


    conn = SSHConnection(
                        # host="192.168.0.50",
                        host="127.0.0.1",
                        port=22,
                        # user="devops",
                        user="vm-connection-test",
                        key_path="/home/njanelidze/.ssh/id_ed25519",
                        script_path_local=f"./{script_name}",
                        script_path_remote=f"/tmp/{script_name}",
                        local_log_file=log_filename,
                        )

    with open(log_filename,"a") as f:
        try:
            conn.connect(timeout=60)
            conn.upload_script()        
            conn.execute(log_output_line, 300,f)
        except RebootNotify as e:
            print(f"ALERT: {e}\nPlease rerun the program")
        except Exception as e:
            print(f"Unexpected error: {e}")
        finally:
            conn.close()



