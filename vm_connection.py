import paramiko
import os
import platform
import socket
from datetime import datetime
import time
import sys
import re

ANSI_ESCAPE = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

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
        # stdin,stdout,stder = self.client.exec_command(f"ssh {self.user}@{self.host} -p {self.port} uptime -s")
        stdin,stdout,stder = self.client.exec_command(f"uptime -s")
        boot = stdout.read().decode().strip()
        boot_time = datetime.strptime(boot, "%Y-%m-%d %H:%M:%S")
        return boot_time

    def connect(self):
        print(f"Trying to connect to {self.host}:{self.port}...")
        try:
            if not self.is_alive(2,5):
                print(f"Could not connect to {self.host}:{self.port}.")
                return False
        except HostUnreachable as e:
            print(f"Could not connect to {self.host}:{self.port}. Error: {e}")
            return False
        
        try:
            self.client = paramiko.SSHClient()
            self.client.load_system_host_keys()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(hostname=self.host,port=self.port,username=self.user,key_filename=self.key_path)
            print("Connection successfull.")
            return True
        except Exception as e:
            print(f"Failed to connect.\nError: {e}")
            return False
        
    def reconnect(self,retries,delay):
        for _ in range(retries):
            if self.connect():
                self.boot_after = self.get_boot()
                # self.boot_after = datetime.strptime("2025-08-11 12:40:30","%Y-%m-%d %H:%M:%S")
                return True
            

        raise HostUnreachable("All reconnection attemtps failed")
                    

    def is_alive(self,retries,delay):
        print("Checking if host machine is active...")
        for i in range (1,retries+1):
            ping_check = False
            socket_check = False
            ssh_check = False

            print(f"Try {i}: Checking connections")
            
            if  os.system(f"ping -c 3 {self.host} > /dev/null 2>&1") == 0: ping_check = True
            print(f"    Ping check status: {ping_check}")

            try:
                with socket.create_connection((self.host,self.port),timeout=3):
                    socket_check = True
                    print(f"    Socket  check status: {socket_check}")
            except Exception:
                    print(f"    Socket  check status: {socket_check}")
                    socket_check = False

            if os.system(f"ssh -o ConnectTimeout=5 {self.user}@{self.host} -p {self.port} whoami > /dev/null 2>&1") == 0: ssh_check = True
            print(f"    SSH check status: {ssh_check}")

            if ping_check or socket_check or ssh_check: 
                print(f"Host {self.host} on port {self.port} is active.")
                return True
            else: 
                time.sleep(delay)
            
        raise HostUnreachable(f"Host {self.host} on port {self.port} is unreachable after multiple retries.")


    def upload_script(self):
            sftp = self.client.open_sftp()
            sftp.put(self.script_path_local, self.script_path_remote)
            sftp.close()
            _,_,stderr = self.client.exec_command(f"chmod +x {self.script_path_remote}")
            error = stderr.read().decode().strip()
            if error:
                raise PermissionError("chmod +x failed. Check if file was uploaded")
            else:
                print(f"Script: {self.script_path_local} uploaded to {self.host}:{self.script_path_remote}")
        

        
    def execute(self,log_output_line,timeout):
        transport_name = self.client.get_transport()
        channel = transport_name.open_session()
        channel.get_pty()


        self.boot_before = self.get_boot()


        print("Starting process...")
        channel.exec_command(f"screen -S script_execution {self.script_path_remote}")
        # channel.exec_command(f"screen -c /dev/null -S script_execution {self.script_path_remote}")

        last_activity  = time.time()
        data_stdout = ""
        try:
            print("Starting process...")
            while True:
                while channel.recv_ready():
                    data_stdout += channel.recv(1024).decode()
                    while "\n" in data_stdout:
                        line, data_stdout = data_stdout.split("\n",1)
                        log_output_line(line,self.local_log_file)
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
                # return self.exit_status
                time.sleep(0.1)

        except Exception as e:
            print(f"Error during streaming / Connection lost:{e}\n")
            return self.execute_after_reconnect(log_output_line,timeout)

    def execute_after_reconnect(self,log_output_line,timeout):
        try:
            if not self.reconnect(3,5):
                print("Reconnection attempts failed")
                return -10
        except HostUnreachable as e:
            print(f"Reconnect failed: {e}")
            return -10
        
        reconnected_transport_name = self.client.get_transport()
        channel = reconnected_transport_name.open_session()
        channel.get_pty()
        channel.exec_command(f"screen -r script_execution")

        last_activity  = time.time()
        data_stdout = ""
        log_output_line(f"{datetime.now()}",self.local_log_file)
        print("Connection restored to 'screen' session. streaming the output...")
        try:
            while True:
                while channel.recv_ready():
                    data_stdout += channel.recv(1024).decode()
                    while "\n" in data_stdout:
                        line, data_stdout = data_stdout.split("\n",1)
                        log_output_line(line,self.local_log_file)
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
                # return self.exit_status
                time.sleep(0.1)

        except Exception as e:
            print(f"Error during streaming / Connection lost:{e}\n")
            return self.execute_after_reconnect(log_output_line,timeout)
            

    def close(self):
        if hasattr(self, 'client'):
            self.client.close()
        else:
            print("No active client to close.")


# ANSI_ESCAPE = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

# def strip_ansi_codes(text):
#     return ANSI_ESCAPE.sub('', text)


def log_output_line(line,local_log_file):
    with open(local_log_file,'a') as f:
        print(f"[REMOTE] >> {line.strip()}")
        f.write(line.strip('\n') + "\n")

if __name__ == "__main__":

    script_name = "script.sh"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    log_filename = f"/tmp/{script_name}_{timestamp}.log"


    conn = SSHConnection(
                        # host="192.168.0.118",
                        host="127.0.0.1",

                        port=22,
                        user="vm-connection-test",
                        key_path="/home/njanelidze/.ssh/id_ed25519",
                        script_path_local=f"./{script_name}",
                        script_path_remote=f"/tmp/{script_name}]",
                        local_log_file=log_filename
                        )

    conn.connect()
    conn.upload_script()

    conn.execute(log_output_line,300)


    # conn.reconnect(1,5)
    # conn.get_boot()
    # conn.is_alive(3,5)

    conn.close()
    # conn.reconnect(3,5)



