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

    def connect(self):
        print(f"Trying to connect to {self.host}:{self.port}...")
        try:
            self.client = paramiko.SSHClient()
            self.client.load_system_host_keys()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(hostname=self.host,port=self.port,username=self.user,key_filename=self.key_path)
            print("Connection successfull")
        except Exception as e:
            print(f"Failed to connect\nError:{e}")
            sys.exit(1)


    def reconnect(self,retries,delay):
            for i in range(retries):
                try:
                    print("Reconnecting")
                    self.connect()
                    self.boot_after = self.get_boot()
                    print("Reconnected")
                    return True
                except Exception as e:
                    print(f"Failed to reconnect.\nError: {e}")
                    time.sleep(delay)
            print("All reconnection attemtps failed")
            return False
                    

    def is_alive(self,retries,delay):
        ping_check = False
        socket_check = False
        ssh_check = False

        print("Checking if host machine is active...")
        for _ in range (retries):
            if  os.system(f"ping -c 3 {self.host} > /dev/null 2>&1") == 0: ping_check = True
            print(f"Ping check status: {ping_check}")

            try:
                with socket.create_connection((self.host,self.port),timeout=3):
                    socket_check = True
                    print(f"Socket  check status: {socket_check}")
            except OSError as e:
                    print(f"Socket  check status: {socket_check}\nError: {e}")
                    socket_check = False
            
            if os.system(f"ssh {self.user}@{self.host} -p {self.port} whoami > /dev/null 2>&1") == 0: ssh_check = True
            print(f"SSH check status: {ssh_check}")

            if ping_check or socket_check or ssh_check: 
                return True
            else: 
                time.sleep(delay)

            raise HostUnreachable("Host is unreachable!!!")
            

        
    def get_boot(self):
        stdin,stdout,stder = self.client.exec_command("uptime -s")
        boot = stdout.read().decode().strip()
        boot_time = datetime.strptime(boot, "%Y-%m-%d %H:%M:%S")
        return boot_time

        
    def execute(self,log_output_line,timeout):
        self.boot_before = self.get_boot()
        transport_name = self.client.get_transport()
        channel = transport_name.open_session()
        channel.get_pty()

        channel.exec_command(
        "bash -c 'set -e; "
        "for i in {0..3}; do echo hello $((i+1)) && sleep 0.5; done; "
        "ls -l /root; "
        "for i in {0..5}; do echo hello $((i+1)) && sleep 0.5; done'"
        )

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

                if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                    break
                elif time.time() - last_activity >= timeout:
                    print("Time exceeded. exiting...")
                    return -5
                time.sleep(0.1)

        except Exception as e:
                    print(f"Error during execution / Connection lost{e}\n")
                    if not self.is_alive(retries=3,delay=5):
                        print("Host is unreachable")

                    if not self.reconnect(3,5):
                        print("Failed to reconnect")
                        return -10
                    
                    if self.boot_before < self.boot_after:
                        raise RebootNotify("Reboot detected when executing scrip!")
                    


   
        
        
        return channel.recv_exit_status()




    def close(self):
        self.client.close()
        
    
def log_output_line(line):
    print(f"[REMOTE] >> {line.strip()}")

    

            
        

        


conn = SSHConnection(
                    host="127.0.0.1",
                    port=22,
                    user="njanelidze",
                    key_path="/home/njanelidze/.ssh/id_ed25519"
                    )

conn.connect()

exit_code = conn.execute(log_output_line,2)
print(exit_code)
conn.get_boot()
conn.close()

if conn.is_alive():
    print("Host machine is active.")

conn.reconnect(3,5)



