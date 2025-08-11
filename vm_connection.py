import paramiko
import os
import platform
import socket
from datetime import datetime
import time
import sys

class RebootNotify(Exception):
    def __init__(self, message):
        self.message = message

class HostUnreachable(Exception):
    def __init__(self, message):
        self.message = message



class SSHConnection:
    def __init__(self,host,port, user, key_path):
        self.host = host
        self.port = port
        self.user = user
        self.key_path = key_path
        self.boot_after = None
        self.boot_before = None

    def get_boot(self):
        stdin,stdout,stder = self.client.exec_command(f"ssh {self.user}@{self.host} -p {self.port} uptime -s")
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
                # self.boot_after = self.get_boot()
                self.boot_after = datetime.strptime("2025-08-11 12:40:30","%Y-%m-%d %H:%M:%S")
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
            
        
    def execute(self,log_output_line,timeout):
        self.boot_before = self.get_boot()
        transport_name = self.client.get_transport()
        channel = transport_name.open_session()
        channel.get_pty()
    
        channel.exec_command(
        "bash -c 'set -e; "
        "for i in {0..1000}; do echo hello $((i+1)) && sleep 0.5; done; "
        "ls -l /root; "
        "for i in {0..5}; do echo hello $((i+1)) && sleep 0.5; done'"
        )

        # channel.exec_command("bash -c 'sleep 100'")

        last_activity  = time.time()
        data_stdout = ""
        data_stderr = ""
        try:
            print("Starting process...")
            while True:
                while channel.recv_ready():
                    data_stdout += channel.recv(1024).decode()
                    while "\n" in data_stdout:
                        line, data_stdout = data_stdout.split("\n",1)
                        # if line.strip():
                        #     log_output_line(line)
                        log_output_line(line)
                        last_activity = time.time()
                    

                while channel.recv_stderr_ready():
                    data_stderr += channel.recv_stderr(1024).decode()
                    while "\n" in data_stderr:
                        line, data_stderr = data_stderr.split("\n",1)
                        # if line.strip():
                        #     log_output_line(line)
                        log_output_line(line)
                        last_activity = time.time()

                if time.time() - last_activity >= timeout:
                    print("Time exceeded. exiting...")
                    return -5
                
                if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                    exit_code = channel.recv_exit_status()
                    if exit_code == -1:
                        raise ConnectionError("SSH connection lost before command finished")
                # return self.exit_status
            time.sleep(0.1)


        except Exception as e:
            print(f"Error during execution / Connection lost:{e}\n")
            if not self.reconnect(3,5):
                return -10
            
            if self.boot_before < self.boot_after:
                print("Reboot detected when executing scrip!") 

    def close(self):
        if hasattr(self, 'client'):
            self.client.close()
        else:
            print("No active client to close.")
        
def log_output_line(line):
    print(f"[REMOTE] >> {line.strip()}")

    

            
        

        


conn = SSHConnection(
                    host="127.0.0.1",
                    port=22,
                    user="njanelidze",
                    key_path="/home/njanelidze/.ssh/id_ed25519"
                    )

conn.connect()
conn.execute(log_output_line,5)


# conn.reconnect(1,5)
# conn.get_boot()
# conn.is_alive(3,5)

conn.close()
# conn.reconnect(3,5)



